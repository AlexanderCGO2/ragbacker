from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel, Field, validator
import os
import tempfile
import shutil
import logging
import requests
import urllib.parse
from requests.auth import HTTPBasicAuth
from llama_index.core.readers import SimpleDirectoryReader
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core.storage import StorageContext
from llama_parse import LlamaParse

# Router setup
ingest_router = APIRouter()

temp_dir = tempfile.mkdtemp()

class Filenames(BaseModel):
    filenames: List[str] = Field(..., example=["file1.txt", "file2.docx"])

class FileLoaderConfig(BaseModel):
    data_dir: str = temp_dir
    use_llama_parse: bool = True

    @validator("data_dir", pre=True, always=True)
    def data_dir_must_exist(cls, v):
        if not os.path.exists(v):
            os.makedirs(v)
        if not os.path.isdir(v):
            raise ValueError(f"Path '{v}' is not a directory")
        return v

def llama_parse_parser():
    if os.getenv("LLAMA_CLOUD_API_KEY") is None:
        raise ValueError("LLAMA_CLOUD_API_KEY environment variable is not set.")
    return LlamaParse(result_type="markdown", verbose=True, language="de")

# Configuration using environment variables
base_url = os.getenv('WEBDAV_URL') + '/files/' + os.getenv('WEBDAV_LOGIN') + '/'
auth = HTTPBasicAuth(os.getenv('WEBDAV_LOGIN'), os.getenv('WEBDAV_PASSWORD'))

def check_and_download_file(filename: str, temp_dir: str):
    """Check if the file exists on the server and download it if it does."""
    url = base_url + urllib.parse.quote(filename)
    headers = {"Depth": "0"}
    propfind_body = '''
    <d:propfind xmlns:d="DAV:">
        <d:prop>
            <d:getcontentlength/>
        </d:prop>
    </d:propfind>
    '''
    with requests.Session() as session:
        session.auth = auth
        response = session.request("PROPFIND", url, headers=headers, data=propfind_body)
        if response.status_code == 207:
            local_path = os.path.join(temp_dir, os.path.basename(filename))
            response_get = session.get(url)
            if response_get.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(response_get.content)
                return local_path
    return None

@ingest_router.post("/process-files", response_model=dict)
def process_files(data: Filenames, config: FileLoaderConfig = Depends()):
    logger = logging.getLogger(__name__)
    processed_documents = []

    try:
        # Download all files first
        downloaded_files = []
        for filename in data.filenames:
            file_path = check_and_download_file(filename, config.data_dir)
            if file_path:
                downloaded_files.append(file_path)
        logger.info(f"Downloaded {len(downloaded_files)} files")

        # Filter out None values if some files failed to download
        valid_files = [file for file in downloaded_files if file]
        logger.info(f"Downloaded {len(valid_files)} files out of {len(data.filenames)}")

        # Proceed only if files are successfully downloaded
        if valid_files:
            reader = SimpleDirectoryReader(config.data_dir, recursive=True)
            if config.use_llama_parse:
                parser = llama_parse_parser()
                supported_file_types = [".pdf", ".doc", ".docx", ".pptx", ".txt", ".rtf", ".pages", ".key", ".epub"]
                reader.file_extractor = {file_type: parser for file_type in supported_file_types}
                processed_documents = reader.load_data()
            logger.info(f"Processed documents: {len(processed_documents)}")

            # Setup Pinecone integration if required
            if config.use_llama_parse:
                store = PineconeVectorStore(
                    api_key=os.getenv("PINECONE_API_KEY"),
                    index_name=os.getenv("PINECONE_INDEX_NAME"),
                    environment=os.getenv("PINECONE_ENVIRONMENT"),
                )
                storage_context = StorageContext.from_defaults(vector_store=store)
        else:
            logger.error("No files were downloaded successfully; skipping processing.")

        return {"message": "Files processed successfully"}

    except Exception as e:
        logger.error(f"Failed to process files due to an error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(config.data_dir):
            shutil.rmtree(config.data_dir)
            logger.info(f"Temporary directory {config.data_dir} cleaned up")

