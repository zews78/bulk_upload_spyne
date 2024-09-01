import boto3
from botocore.exceptions import NoCredentialsError

import requests
from PIL import Image
from io import BytesIO
import base64
from database import update_status, save_compressed_image
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# from database import update_status, save_compressed_image

async def process_images(df, request_id):
    try:
        for index, row in df.iterrows():
            image_urls = row['Input Image Urls'].split(',')
            compressed_urls = []
            
            for url in image_urls:
                # Fetch and compress image
                compressed_url = await compress_and_upload_image(url, row['Product Name'])
                compressed_urls.append(compressed_url)
            
            # Save the result for the product
            save_compressed_image(request_id, row['Product Name'], image_urls, compressed_urls)
            # print(request_id, row['Product Name'], image_urls, compressed_urls)
        
        # Update request status to 'Completed'
        update_status(request_id, "Completed")
        
        # Trigger webhook
        # trigger_webhook(request_id)
    
    except Exception as e:
        update_status(request_id, "Failed", str(e))
    pass


s3_client = boto3.client(
    's3',
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
)
bucket_name = "sharique-s3-bucket"
async def compress_and_upload_image(url, s3_key_prefix=""):
    try:
        # Fetch the image from the URL
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Compress the image
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
        buffered = BytesIO()
        img.save(buffered, format="JPEG", optimize=True, quality=50)
        # buffered.seek(0)
        # print("buffered", buffered)
        # print("\n")
        # Generate the S3 key (path) for the image
        s3_key = f"{s3_key_prefix}/{os.path.basename(url)}"
        print("s3_key", s3_key)

        content_type = response.headers.get('Content-Type', 'image/jpeg')
        
        # Upload the image to S3
        # s3_client.upload_fileobj(buffered, bucket_name, s3_key, ExtraArgs={'ContentType': 'image/jpeg'})
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=buffered.getvalue(),
            ContentType= content_type
        )
        
        # Generate the S3 URL
        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        print("\n")
        print("product-", s3_key_prefix, s3_url)
        return s3_url
    except NoCredentialsError:
        return "Credentials not available"
    except Exception as e:
        return str(e)

# def trigger_webhook(request_id):
#     # Call the webhook endpoint to notify the processing completion
#     webhook_url = "https://your-webhook-url.com"
#     requests.post(webhook_url, json={"request_id": request_id, "status": "Completed"})



# s3_client = boto3.client(
#     's3',
    # aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID'),
    # aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
# )
# bucket_name = "sharique-s3-bucket"

def test_upload_image_to_s3(image_url, bucket_name, s3_filename):
    try:
        # Download the image from the URL
        response = requests.get(image_url)
        response.raise_for_status()  # Ensure the request was successful

        # Initialize the S3 client
        s3 = boto3.client(
            's3',
            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        # Determine the content type
        content_type = response.headers.get('Content-Type', 'image/jpeg')

        # Upload the image to the S3 bucket
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_filename,
            Body=response.content,
           ContentType=content_type
        )

        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_filename}"
        print(f"Image uploaded successfully to {s3_url}")
        return s3_url
    
    except requests.exceptions.RequestException as e:
        print(f"Failed to download image: {e}")
    except NoCredentialsError:
        print("Credentials not available for S3")




async def compress_image(url):
    try:
        # Fetch the image from the URL
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        
        # Compress the image
        img = img.resize((img.width // 2, img.height // 2), Image.ANTIALIAS)
        buffered = BytesIO()
        img.save(buffered, format="JPEG", optimize=True, quality=50)
        buffered.seek(0)
        
        return buffered
    except Exception as e:
        return str(e)
