# FastAPI CSV Compressor

## Overview

This application is designed to process CSV files that include image data. It validates the CSV, compresses the images, uploads them to an S3 bucket, and stores the image URLs and associated data in a MongoDB database. The API provides endpoints to upload files and check the status of the processing.

## Features

- **CSV Validation**: Ensures the CSV file meets the required format.
- **Image Compression**: Reduces image size for optimized storage.
- **S3 Integration**: Uploads compressed images to an AWS S3 bucket.
- **MongoDB Integration**: Stores metadata about images and their URLs.
- **Background Processing**: Handles image processing asynchronously.

## How to Run the Application

### Prerequisites

- Python 3.8+
- FastAPI
- Uvicorn
- MongoDB
- AWS S3 Bucket

### Installation

1. Clone this repository:
    ```bash
    git clone https://github.com/your-username/fastapi-csv-processor.git
    cd fastapi-csv-processor
    ```

2. Create a virtual environment and activate it:
    ```bash
    python3 -m venv env
    source env/bin/activate  # On Windows use `env\Scripts\activate`
    ```

3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4. Set up your environment variables for AWS and MongoDB:
    ```bash
    export AWS_ACCESS_KEY_ID='your-access-key-id'
    export AWS_SECRET_ACCESS_KEY='your-secret-access-key'
    export MONGO_URI='your-mongo-uri'
    export S3_BUCKET_NAME='your-s3-bucket-name'
    ```

### Running the Application

1. Start the FastAPI server:
    ```bash
    uvicorn main:app --reload
    ```

2. Access the API documentation at `http://localhost:8000/docs`.

## API Documentation

### POST /upload/

- **Description**: Uploads a CSV file for processing.
- **Request**: Multipart form-data with a file field.
- **Response**: JSON with request ID and processing status.

### GET /status/{request_id}

- **Description**: Checks the processing status of a specific request.
- **Response**: JSON with status details.

## Activity Diagram

Below is the activity diagram representing the workflow of the application:

![Activity Diagram](./test_data/Screenshot%202024-09-02%20044317.png)

## Screenshots

### Successful API Hits
![Upload Screenshot](./test_data/Screenshot%202024-09-02%20025327.png)

### Successful File Upload
![Upload Screenshot](./test_data/Screenshot%202024-09-02%20022324.png)

### Successful push to DB
![Upload Screenshot](./test_data/Screenshot%202024-09-02%20030700.png)

### API Documentation Page
![API Documentation](./test_data/Screenshot%202024-09-02%20033430.png)

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.
