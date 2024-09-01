from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from pydantic import BaseModel
import pandas as pd
from uuid import uuid4
# from image_processor import process_images
# from database import insert_request, get_status
import os
from io import BytesIO
# from fastapi import FastAPI

#import files
from utils import validate_csv
from database import insert_request, get_status
from image_processor import process_images, test_upload_image_to_s3, compress_image, compress_and_upload_image
# from image_processor import test_upload_image_to_s3



app = FastAPI()

class StatusResponse(BaseModel):
    request_id: str
    status: str
    message: str

@app.post("/upload/")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
# async def upload_file(file: UploadFile = File(...)):

    try:
        # Generate a unique request ID
        request_id = str(uuid4())
        
        # Read the CSV file
        df = pd.read_csv(file.file)
        
        # Validate CSV
        validate_csv(df)
        
        # Save request to the database
        insert_request(request_id, df.to_dict(orient='records'))
        
        # Start background processing
        background_tasks.add_task(process_images, df, request_id)
        # await process_images(df, request_id)
        
        return {"request_id": request_id, "status": "Processing started."}
    
    except Exception as e:
        return {"error": str(e)}

@app.get("/status/{request_id}", response_model=StatusResponse)
async def get_processing_status(request_id: str):
    status = get_status(request_id)
    return status

# Webhook endpoint to be implemented
# @app.post("/webhook/")
# async def webhook(data: dict):
#     # Handle webhook notifications
#     pass


#test my fist fastapi
@app.get("/")
async def read_root():
    # image_url = 'https://sharique-s3-bucket.s3.us-west-2.amazonaws.com/dau_ui+(2).jpeg'
    # bucket_name = 'sharique-s3-bucket'
    # s3_key_prefix = 'testimages/test_myimage.jpeg'
    # uploaded_s3_url = test_upload_image_to_s3(image_url, bucket_name, s3_key_prefix)
    # print("Uploaded S3 URL:", uploaded_s3_url)    
    # return {"example": "hello World", "url": uploaded_s3_url}


    url = "https://sharique-s3-bucket.s3.us-west-2.amazonaws.com/Capture.PNG"
    # compressed_image = await compress_image(url)
    
    # if isinstance(compressed_image, BytesIO):
    #     # Convert BytesIO to byte string
    #     byte_data = compressed_image.getvalue()
    #     print(byte_data)
    # else:
    #     # Print the error message
    #     print(compressed_image)
    s3_url = await compress_and_upload_image(url, "test_SKU2")
    return {"example": "hello World", "url": s3_url}


    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
