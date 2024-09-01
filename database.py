import pymongo
from dotenv import load_dotenv
import os
#----------------------------------------

from pymongo.mongo_client import MongoClient
# from pymongo.server_api import ServerApi
# Load environment variables from .env file
load_dotenv()

uri = os.getenv('MONGO_URI')

# Create a new client and connect to the server
client = MongoClient(uri)

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)



#========================================



# client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["image_db"]
requests_collection = db["requests"]

def insert_request(request_id, data):
    requests_collection.insert_one({"_id": request_id, "raw_data": data, "status": "Processing", "message": ""})

def update_status(request_id, status, message=""):
    requests_collection.update_one({"_id": request_id}, {"$set": {"status": status, "message": message}})

def save_compressed_image(request_id, product_name, input_urls, output_urls):
    requests_collection.update_one(
        {"_id": request_id},
        {"$push": {"data": {"product_name": product_name, "input_urls": input_urls, "output_urls": output_urls}}}
    )

def get_status(request_id):
    request = requests_collection.find_one({"_id": request_id})
    if request:
        return {"request_id": request_id, "status": request["status"], "message": request["message"]}
    else:
        return {"request_id": request_id, "status": "Not found", "message": ""}
