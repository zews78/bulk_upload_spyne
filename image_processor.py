# import boto3
import asyncio
import aiohttp  # Replace requests
import aioboto3  # Async boto3
from concurrent.futures import ThreadPoolExecutor

# import requests
from PIL import Image
from io import BytesIO
# import base64
from database import update_status, save_compressed_image
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# from database import update_status, save_compressed_image

async def process_images(df, request_id):
    """Process all products concurrently"""
    try:
        # Create tasks for all products - CONCURRENT
        tasks = [process_single_product(row, request_id) for _, row in df.iterrows()]
        await asyncio.gather(*tasks)  # Run all products simultaneously
        
        update_status(request_id, "Completed")
    except Exception as e:
        update_status(request_id, "Failed", str(e))

async def process_single_product(row, request_id):
    """Process all images for one product concurrently"""
    image_urls = row['Input Image Urls'].split(',')
    
    # Process all URLs for this product simultaneously - CONCURRENT
    tasks = [compress_and_upload_image(url, row['Product Name']) for url in image_urls]
    compressed_urls = await asyncio.gather(*tasks)
    
    save_compressed_image(request_id, row['Product Name'], image_urls, compressed_urls)


bucket_name = "sharique-s3-bucket"

async def compress_and_upload_image(url, s3_key_prefix=""):
    """Async image processing with proper concurrency"""
    try:
        # 1. ASYNC HTTP REQUEST - Non-blocking
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()  # Check for HTTP errors
                content = await response.read()
        
        # 2. CPU-BOUND WORK IN THREAD POOL - Non-blocking
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            processed_image = await loop.run_in_executor(
                executor, 
                process_image_sync, 
                content
            )
        
        # 3. ASYNC S3 UPLOAD - Non-blocking
        s3_key = f"{s3_key_prefix}/{os.path.basename(url)}"
        session = aioboto3.Session(
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        async with session.client('s3') as s3:
            await s3.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=processed_image.getvalue(),
                ContentType='image/jpeg'
            )
        
        return f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
    
    except aiohttp.ClientError as e:
        return f"HTTP error: {str(e)}"
    except Exception as e:
        return f"Processing error: {str(e)}"


# def trigger_webhook(request_id):
#     # Call the webhook endpoint to notify the processing completion
#     webhook_url = "https://your-webhook-url.com"
#     requests.post(webhook_url, json={"request_id": request_id, "status": "Completed"})




def process_image_sync(content):
    """Synchronous image processing - runs in thread pool"""
    img = Image.open(BytesIO(content))
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
    buffered = BytesIO()
    img.save(buffered, format="JPEG", optimize=True, quality=50)
    return buffered
