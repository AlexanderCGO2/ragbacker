from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel, Field
import os
import tempfile
import shutil
import logging
import requests
import urllib.parse
from app.api.routers.metadata import extract_metadata_and_text
from requests.auth import HTTPBasicAuth

# Router setup
ingest_router = APIRouter()

class Filenames(BaseModel):
    filenames: List[str] = Field(..., example=["file1.txt", "file2.docx"])

# Configuration using environment variables
base_url = os.getenv('WEBDAV_URL') + '/files/' + os.getenv('WEBDAV_LOGIN') + '/'
auth = HTTPBasicAuth(os.getenv('WEBDAV_LOGIN'), os.getenv('WEBDAV_PASSWORD'))

def check_and_download_file(filename: str, temp_dir: str):
    """Check if the file exists on the server and download it if it does."""
    url = base_url + urllib.parse.quote(filename)
    # Check if file exists using PROPFIND
    headers = {"Depth": "0"}
    propfind_body = '''
    <d:propfind xmlns:d="DAV:">
    <d:prop>
        <d:getcontentlength/>
    </d:prop>
    </d:propfind>
    '''
    response = requests.request("PROPFIND", url, headers=headers, data=propfind_body, auth=auth)
    if response.status_code == 207:
        # File exists, download it
        local_path = os.path.join(temp_dir, os.path.basename(filename))
        response_get = requests.get(url, auth=auth)
        if response_get.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response_get.content)
            return local_path
    return None

@ingest_router.post("/process-files", response_model=dict)
async def process_files(data: Filenames):
    logger = logging.getLogger(__name__)
    temp_dir = tempfile.mkdtemp()
    processed_documents = []
    try:
        for filename in data.filenames:
            logger.info(f"Checking and downloading file: {filename}")
            file_path = check_and_download_file(filename, temp_dir)
            if file_path:
                metadata_and_text = extract_metadata_and_text(file_path)
                processed_documents.append(metadata_and_text)
            else:
                logger.warning(f"File not found on server: {filename}")
        return {"message": "Files processed successfully", "data": processed_documents}
    except Exception as e:
        logger.error(f"Failed to process files due to an error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir)

