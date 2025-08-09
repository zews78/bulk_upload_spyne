import asyncio
import aiohttp
import aioboto3
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from io import BytesIO
from database import update_status, save_compressed_image
import os
from dotenv import load_dotenv
import time
from contextlib import asynccontextmanager

load_dotenv()

# Global configuration
MAX_CONCURRENT_IMAGES = 50  # Limit concurrent image processing
MAX_CONCURRENT_PRODUCTS = 5  # Limit concurrent product processing
MAX_RETRIES = 3
RETRY_DELAY = 1
REQUEST_TIMEOUT = 30
THREAD_POOL_SIZE = 20
DELAY_BETWEEN_REQUESTS = 0.5  # 100ms delay

bucket_name = "bulk-import-dada"

# Global resources
_http_session = None
_s3_session = None
_thread_pool = None
_image_semaphore = None
_product_semaphore = None

async def initialize_resources():
    """Initialize global resources once"""
    global _http_session, _s3_session, _thread_pool, _image_semaphore, _product_semaphore
    
    if _http_session is None:
        # Optimized HTTP session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=55,  # Max connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        _http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'BulkUploader/1.0'}
        )
    
    if _s3_session is None:
        _s3_session = aioboto3.Session(
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name='ap-south-1'
        )
    
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)
    
    if _image_semaphore is None:
        _image_semaphore = asyncio.Semaphore(MAX_CONCURRENT_IMAGES)
    
    if _product_semaphore is None:
        _product_semaphore = asyncio.Semaphore(MAX_CONCURRENT_PRODUCTS)

async def cleanup_resources():
    """Cleanup global resources"""
    global _http_session, _thread_pool
    
    if _http_session:
        await _http_session.close()
        _http_session = None
    
    if _thread_pool:
        _thread_pool.shutdown(wait=True)
        _thread_pool = None

async def process_images(df, request_id):
    """Process all products with proper resource management"""
    try:
        await initialize_resources()
        
        print(f"Starting to process {len(df)} products for request_id: {request_id}")
        
        # Process products in batches to prevent memory overflow
        batch_size = 5
        total_products = len(df)
        
        for i in range(0, total_products, batch_size):
            batch = df.iloc[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(total_products + batch_size - 1)//batch_size}")
            
            tasks = [process_single_product_with_semaphore(row, request_id) 
                    for _, row in batch.iterrows()]
            
            # Use return_exceptions=True to handle individual failures
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any exceptions but continue processing
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"Error processing product {i + idx}: {result}")
        
        print("All tasks completed!")
        update_status(request_id, "Completed")
        
    except Exception as e:
        print(f"Critical error in process_images: {e}")
        update_status(request_id, "Failed", str(e))
    finally:
        # Don't cleanup here if using global session
        pass

async def process_single_product_with_semaphore(row, request_id):
    """Process single product with concurrency control"""
    async with _product_semaphore:
        return await process_single_product(row, request_id)

async def process_single_product(row, request_id):
    """Process all images for one product with better error handling"""
    try:
        image_urls = [url.strip() for url in row['Input Image Urls'].split(',') if url.strip()]
        
        if not image_urls:
            print(f"No valid URLs for product: {row['Product Name']}")
            return
        
        # Process images with controlled concurrency
        tasks = [compress_and_upload_image_with_semaphore(url, row['Product Name']) 
                for url in image_urls]
        
        compressed_urls = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failed uploads but save successful ones
        successful_urls = []
        for i, result in enumerate(compressed_urls):
            if isinstance(result, Exception):
                print(f"Failed to process {image_urls[i]}: {result}")
                successful_urls.append(f"ERROR: {str(result)}")
            else:
                successful_urls.append(result)
        
        save_compressed_image(request_id, row['Product Name'], image_urls, successful_urls)
        
    except Exception as e:
        print(f"Error processing product {row.get('Product Name', 'Unknown')}: {e}")

async def compress_and_upload_image_with_semaphore(url, s3_key_prefix=""):
    """Wrapper with semaphore for image processing"""
    async with _image_semaphore:
        # Add delay to avoid overwhelming servers
        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
        return await compress_and_upload_image_with_retry(url, s3_key_prefix)

async def compress_and_upload_image_with_retry(url, s3_key_prefix=""):
    """Image processing with exponential backoff retry"""
    for attempt in range(MAX_RETRIES):
        try:
            result = await compress_and_upload_image(url, s3_key_prefix)
            if attempt > 0:  # Log successful retries
                print(f"🔁 Entered on retry {attempt} for {url}")
            return result
        except Exception as e:
            error_msg = str(e).lower()
            print(f"❌ ATTEMPT {attempt + 1} FAILED for {url}: {error_msg}")
            # Handle specific HTTP errors
            if "429" in error_msg:  # Rate limited
                wait_time = RETRY_DELAY * (3 ** attempt)  # Longer backoff for rate limits
                print(f"Rate limited on {url}, waiting {wait_time}s before retry {attempt + 1}")
            elif "307" in error_msg:  # Redirect - might succeed on retry
                wait_time = RETRY_DELAY * (2 ** attempt)
                print(f"Redirect error on {url}, retrying in {wait_time}s")
            elif "422" in error_msg:  # Unprocessable - unlikely to succeed
                print(f"Unprocessable entity for {url}, skipping retries")
                raise e
            else:
                wait_time = RETRY_DELAY * (2 ** attempt)
            
            if attempt == MAX_RETRIES - 1:
                raise e
                
            await asyncio.sleep(wait_time)

async def compress_and_upload_image(url, s3_key_prefix=""):
    """Optimized async image processing"""
    try:
        # 1. ASYNC HTTP REQUEST with global session
        # Enable automatic redirects
        async with _http_session.get(url, allow_redirects=True, max_redirects=3) as response:
            # Handle specific status codes
            if response.status == 429:
                raise Exception(f"429 Too Many Requests for {url}")
            elif response.status == 422:
                raise Exception(f"422 Unprocessable Entity for {url}")
            elif response.status >= 400:
                raise Exception(f"HTTP {response.status} for {url}")
                
            response.raise_for_status()
            content = await response.read()
            
            # Validate content size (prevent memory issues)
            if len(content) > 50 * 1024 * 1024:  # 50MB limit
                raise ValueError(f"Image too large: {len(content)} bytes")
        
        # 2. CPU-BOUND WORK IN THREAD POOL
        loop = asyncio.get_event_loop()
        processed_image = await loop.run_in_executor(
            _thread_pool, 
            process_image_sync, 
            content
        )
        
        # 3. ASYNC S3 UPLOAD with global session
        s3_key = f"{s3_key_prefix}/{int(time.time())}_{os.path.basename(url)}"
        
        async with _s3_session.client('s3') as s3:
            await s3.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=processed_image.getvalue(),
                ContentType='image/jpeg',
                # Add metadata for better management
                Metadata={
                    'original_url': url,
                    'processed_time': str(int(time.time()))
                }
            )
        
        return f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
    
    except aiohttp.ClientError as e:
        raise Exception(f"HTTP error for {url}: {str(e)}")
    except Exception as e:
        raise Exception(f"Processing error for {url}: {str(e)}")

def process_image_sync(content):
    """Optimized synchronous image processing"""
    try:
        img = Image.open(BytesIO(content))
        
        # Handle different image modes
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Smart resizing - don't make tiny images smaller
        width, height = img.size
        if width > 800 or height > 800:
            # Maintain aspect ratio
            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        
        # Optimize compression based on image size
        quality = 85 if img.size[0] * img.size[1] < 500000 else 70
        
        buffered = BytesIO()
        img.save(
            buffered, 
            format="JPEG", 
            optimize=True, 
            quality=quality,
            progressive=True  # For better web loading
        )
        buffered.seek(0)
        return buffered
        
    except Exception as e:
        raise Exception(f"Image processing failed: {str(e)}")