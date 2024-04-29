from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
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
from llama_index.core.indices import VectorStoreIndex
from llama_parse import LlamaParse
import firebase_admin
import base64
from firebase_admin import credentials, firestore


def initialize_firebase():
    # Decode the base64 encoded JSON credentials
    encoded_credentials = os.getenv('FIREBASE_CREDENTIALS_BASE64')
    decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
    firebase_credentials = json.loads(decoded_credentials)

    # Initialize Firebase with the decoded credentials
    cred = credentials.Certificate(firebase_credentials)
    initialize_app(cred)


# Initialize Firebase
initialize_firebase()

db = firestore.client()

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


# sinngle file upload
@ingest_router.post("/upload-file", response_model=dict)
def upload_file(file: UploadFile = File(...), config: FileLoaderConfig = Depends()):
    logger = logging.getLogger(__name__)
    file_path = os.path.join(config.data_dir, file.filename)
    try:
        # Save uploaded file
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        
        logger.info(f"Uploaded {file.filename} to {file_path}")

        # Process the file using SimpleDirectoryReader, similar to /process-files
        if config.use_llama_parse:
            reader = SimpleDirectoryReader(config.data_dir, recursive=True)
            parser = llama_parse_parser()
            supported_file_types = [".pdf", ".doc", ".docx", ".pptx", ".txt", ".rtf", ".pages", ".key", ".epub"]
            reader.file_extractor = {file_type: parser for file_type in supported_file_types}
            processed_documents = reader.load_data()

            # Setup Pinecone integration if required
            if config.use_llama_parse:
                store = PineconeVectorStore(
                    api_key=os.getenv("PINECONE_API_KEY"),
                    index_name=os.getenv("PINECONE_INDEX_NAME"),
                    environment=os.getenv("PINECONE_ENVIRONMENT"),
                )
            storage_context = StorageContext.from_defaults(vector_store=store)
            VectorStoreIndex.from_documents(
            processed_documents,
            storage_context=storage_context,
            show_progress=True,  # this will show you a progress bar as the embeddings are created
            )

            doc_ref = db.collection('ingestedDocs').document(file.filename)
            doc_ref.set({
            'filename': file.filename,
            'status': 'processed',
            # Add more metadata as needed
        })

        return {"message": "File processed and added to Firestore successfully"}

    except Exception as e:
        logger.error(f"Failed to upload and process file due to an error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Cleanup the temporary directory
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up file at {file_path}")



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
            VectorStoreIndex.from_documents(
            processed_documents,
            storage_context=storage_context,
            show_progress=True,  # this will show you a progress bar as the embeddings are created
            )
            # Store documents metadata in Firestore
            if processed_documents:
                # Assuming `processed_documents` are indexed the same as `valid_files`
                for i, doc in enumerate(processed_documents):
                    filename = os.path.basename(valid_files[i])
                    doc_data = {
                        'filename': filename,
                        'content': str(doc),  # or any other method to serialize the document
                        'status': 'processed'
                    }
                    doc_ref = db.collection('ingestedDocs').document(filename)
                    doc_ref.set(doc_data)

        return {"message": "Files processed and data added to Firestore successfully"}

   

    except Exception as e:
        logger.error(f"Failed to process files due to an error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(config.data_dir):
            shutil.rmtree(config.data_dir)
            logger.info(f"Temporary directory {config.data_dir} cleaned up")

