from fastapi import FastAPI, HTTPException, APIRouter, Depends
from webdav3.client import Client
from dotenv import load_dotenv
import os
import tempfile
import shutil
import logging

from app.api.routers.metadata import extract_metadata_and_text  # Importing from metadata.py
from pydantic import BaseModel, Field
from typing import List

class Filenames(BaseModel):
    filenames: List[str] = Field(..., example=["file1.txt", "file2.docx"])
# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration for the WebDAV client
options = {
    'webdav_hostname': os.getenv('WEBDAV_URL') + '/files/' + os.getenv('WEBDAV_LOGIN') + '/',
    'webdav_login': os.getenv('WEBDAV_LOGIN'),
    'webdav_password': os.getenv('WEBDAV_PASSWORD')
}
client = Client(options)
ingest_router = r = APIRouter()

@r.post("/process-files", response_model=dict)
async def process_files(data: Filenames):
    logger.info(f"Received filenames: {data.filenames}")
    temp_dir = tempfile.mkdtemp()
    processed_documents = []
    try:
        for filename in data.filenames:
            local_path = os.path.join(temp_dir, os.path.basename(filename))
            client.download_sync(remote_path=filename, local_path=local_path)
            metadata_and_text = extract_metadata_and_text(local_path)
            processed_documents.append(metadata_and_text)
        return {"message": "Files processed successfully", "data": processed_documents}
    except Exception as e:
        logger.error(f"Failed to process files due to an error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir)
