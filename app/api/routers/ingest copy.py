from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel, Field
import os
import llama_index
import tempfile
import shutil
import logging
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
from app.api.routers.ingest import FileLoaderConfig
# Router setup
ingest_router = APIRouter()

temp_dir = tempfile.mkdtemp()
class Filenames(BaseModel):
    filenames: List[str] = Field(..., example=["file1.txt", "file2.docx"])

class FileLoaderConfig(BaseModel):
    data_dir: str = "temp_dir"
    use_llama_parse: bool = True

    @validator("data_dir")
    def data_dir_must_exist(cls, v):
        if not os.path.isdir(v):
            raise ValueError(f"Directory '{v}' does not exist")
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
    
    processed_documents = []
    for filename in data.filenames:
                        logger.info(f"Checking and downloading file: {filename}")
                        file_path = check_and_download_file(filename, temp_dir)
                        if file_path:
                            # metadata_and_text = extract_metadata_and_text(file_path)
                            # processed_documents.append(metadata_and_text)
                            logger.info(f"File downloaded successfully: {filename}")
                        reader = SimpleDirectoryReader(
                        FileLoaderConfig.data_dir,  # Fix: Use FileLoaderConfig.data_dir instead of config.data_dir
                        recursive=True,
                        )
                )
    if  config.use_llama_parse:
                parser = llama_parse_parser()
                # Unterstützung für mehrere Dateitypen hinzufügen
                supported_file_types = [".pdf", ".doc", ".docx", ".pptx", ".txt", ".rtf", ".pages", ".key", ".epub" ]  # Erweitern Sie diese Liste nach Bedarf
                reader.file_extractor = {file_type: parser for file_type in supported_file_types}
                processed_documents = reader.load_data()
        # to pinecone
        store = PineconeVectorStore(
        api_key=os.environ["PINECONE_API_KEY"],
        index_name=os.environ["PINECONE_INDEX_NAME"],
        environment=os.environ["PINECONE_ENVIRONMENT"],
        )
        storage_context = StorageContext.from_defaults(vector_store=store)
        VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True,  # this will show you a progress bar as the embeddings are created
        )
        return {"message": "Files processed successfully", "documents": processed_documents}
    except Exception as e:
        logger.error(f"Failed to process files due to an error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir)

