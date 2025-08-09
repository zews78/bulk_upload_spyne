from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from pydantic import BaseModel
import pandas as pd
from uuid import uuid4
import asyncio
from contextlib import asynccontextmanager
from io import BytesIO

# Import files
from utils import validate_csv
from database import insert_request, get_status
from image_processor import process_images, cleanup_resources

# Global task tracking
active_tasks = {}
MAX_CONCURRENT_UPLOADS = 20  # Limit concurrent file uploads

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    yield
    # Shutdown
    print("Shutting down...")
    await cleanup_resources()
    # Cancel any remaining tasks
    for task in active_tasks.values():
        if not task.done():
            task.cancel()

app = FastAPI(lifespan=lifespan)

class StatusResponse(BaseModel):
    request_id: str
    status: str
    message: str

@app.post("/upload/")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # Check if we're at capacity
    if len(active_tasks) >= MAX_CONCURRENT_UPLOADS:
        raise HTTPException(
            status_code=429, 
            detail="Server is at capacity. Please try again later."
        )
    
    try:
        # Validate file type and size
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
        # Generate a unique request ID
        request_id = str(uuid4())
        
        # Read the CSV file with size limit
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=413, detail="File too large")
        
        df = pd.read_csv(BytesIO(content))
        
        # Validate CSV
        validate_csv(df)
        
        # Save request to the database
        insert_request(request_id, df.to_dict(orient='records'))

        # Create and track background task
        task = asyncio.create_task(process_images(df, request_id))
        active_tasks[request_id] = task
        
        # Clean up completed tasks
        def cleanup_task(task_id):
            active_tasks.pop(task_id, None)
        
        task.add_done_callback(lambda t: cleanup_task(request_id))
        
        return {"request_id": request_id, "status": "Processing started."}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

@app.get("/status/{request_id}", response_model=StatusResponse)
async def get_processing_status(request_id: str):
    status = get_status(request_id)
    
    # Add real-time task status if available
    if request_id in active_tasks:
        task = active_tasks[request_id]
        if not task.done():
            status["message"] = f"{status.get('message', '')} (Active)"
    
    return status

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "active_uploads": len(active_tasks),
        "capacity": MAX_CONCURRENT_UPLOADS
    }

@app.get("/")
async def read_root():
    return {"message": "FastAPI CSV Compressor", "active_tasks": len(active_tasks)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        workers=1,  # Single worker for shared state
        loop="uvloop",  # Better performance on Linux
        access_log=False  # Disable for better performance
    )