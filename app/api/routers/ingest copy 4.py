from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel, Field
import os
import llama_index
import tempfile
import shutil
import logging
import aiohttp 
import requests
import urllib.parse
from app.api.routers.metadata import extract_metadata_and_text
from requests.auth import HTTPBasicAuth
from llama_index.core.readers import SimpleDirectoryReader
import logging
# logging.basicConfig(level=logging.DEBUG)
from llama_index.core.storage import StorageContext
from llama_index.core.indices import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from fastapi import Depends
from llama_parse import LlamaParse
from pydantic import BaseModel, validator
import nest_asyncio
import asyncio

nest_asyncio.apply()

# Router setup
ingest_router = APIRouter()

temp_dir = tempfile.mkdtemp()
class Filenames(BaseModel):
    filenames: List[str] = Field(..., example=["file1.txt", "file2.docx"])

class FileLoaderConfig(BaseModel):
    data_dir: str = "temp_dir"
    use_llama_parse: bool = True

    @validator("data_dir", pre=True, always=True)
    def data_dir_must_exist(cls, v):
        if not os.path.exists(v):
            os.makedirs(v)  # Create the directory if it does not exist
        if not os.path.isdir(v):
            raise ValueError(f"Path '{v}' is not a directory")
        return v



def llama_parse_parser():
    if os.getenv("LLAMA_CLOUD_API_KEY") is None:
        raise ValueError(
            "LLAMA_CLOUD_API_KEY environment variable is not set. "
            "Please set it in .env file or in your shell environment then run again!"
        )
    parser = LlamaParse(result_type="markdown", verbose=True, language="en")
    return parser
# Configuration using environment variables
base_url = os.getenv('WEBDAV_URL') + '/files/' + os.getenv('WEBDAV_LOGIN') + '/'
auth = HTTPBasicAuth(os.getenv('WEBDAV_LOGIN'), os.getenv('WEBDAV_PASSWORD'))

async def check_and_download_file(filename: str, temp_dir: str):
    """Asynchronously check if the file exists on the server and download it if it does."""
    url = base_url + urllib.parse.quote(filename)
    headers = {"Depth": "0"}
    propfind_body = '''
    <d:propfind xmlns:d="DAV:">
        <d:prop>
            <d:getcontentlength/>
        </d:prop>
    </d:propfind>
    '''
    async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(os.getenv('WEBDAV_LOGIN'), os.getenv('WEBDAV_PASSWORD'))) as session:
        async with session.request("PROPFIND", url, headers=headers, data=propfind_body) as response:
            if response.status == 207:
                local_path = os.path.join(temp_dir, os.path.basename(filename))
                async with session.get(url) as response_get:
                    if response_get.status == 200:
                        with open(local_path, 'wb') as f:
                            while True:
                                chunk = await response_get.content.read(1024)
                                if not chunk:
                                    break
                                f.write(chunk)
                        return local_path
    return None

@ingest_router.post("/process-files", response_model=dict)
async def process_files(data: Filenames, config: FileLoaderConfig = Depends()):
    logger = logging.getLogger(__name__)
    processed_documents = []

    try:
        # Ensure the temporary directory is correct
        if not os.path.exists(config.data_dir):
            os.makedirs(config.data_dir)
            logger.info(f"Created temporary directory at {config.data_dir}")

        # Download all files first
        download_tasks = [check_and_download_file(filename, config.data_dir) for filename in data.filenames]
        downloaded_files = await asyncio.gather(*download_tasks)
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
            if config.use_llama_parse:  # Assuming using Pinecone depends on this config
                store = PineconeVectorStore(
                    api_key=os.getenv("PINECONE_API_KEY"),
                    index_name=os.getenv("PINECONE_INDEX_NAME"),
                    environment=os.getenv("PINECONE_ENVIRONMENT"),
                )
                storage_context = StorageContext.from_defaults(vector_store=store)
                VectorStoreIndex.from_documents(
                    processed_documents,
                    storage_context=storage_context,
                    show_progress=True,
                )
        else:
            logger.error("No files were downloaded successfully; skipping processing.")
        
        return {"message": "Files processed successfully", "documents": processed_documents}

    except Exception as e:
        logger.error(f"Failed to process files due to an error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(config.data_dir):
            shutil.rmtree(config.data_dir)
            logger.info(f"Temporary directory {config.data_dir} cleaned up")

