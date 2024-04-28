from fastapi import FastAPI, HTTPException, APIRouter
from webdav3.client import Client
from dotenv import load_dotenv
import os
import tempfile
import shutil
from llama_index.core.readers import SimpleDirectoryReader
from llama_parse import LlamaParse
import logging


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration for the WebDAV client
options = {
    'webdav_hostname': os.getenv('WEBDAV_URL') + '/files/' + os.getenv('WEBDAV_LOGIN') + '/',
    'webdav_login':    os.getenv('WEBDAV_LOGIN'),
    'webdav_password': os.getenv('WEBDAV_PASSWORD')
}
client = Client(options)
ingest_router = r = APIRouter()

llama_parser = LlamaParse()  # Initialize your LlamaParse or similar tool

def extract_metadata_and_text(file_path):
    # Include the metadata extraction logic here as previously described
    pass

@r.post("/process-files/")
async def process_files(filenames: list):
    temp_dir = tempfile.mkdtemp()
    processed_documents = []
    try:
        for filename in filenames:
            local_path = os.path.join(temp_dir, os.path.basename(filename))
            client.download_sync(remote_path=filename, local_path=local_path)
            
            # Use LlamaParse or SimpleDirectoryReader based on the file type
            file_extension = os.path.splitext(local_path)[1].lower()
            if file_extension in [".pdf", ".docx", ".pptx"]:
                # Process files with LlamaParse
                metadata_and_text = extract_metadata_and_text(local_path)
                processed_documents.append(metadata_and_text)
            else:
                # Use default file processing for unsupported types
                reader = SimpleDirectoryReader(local_path)
                documents = reader.load_data()
                for doc in documents:
                    metadata_and_text = extract_metadata_and_text(doc.file_path)
                    processed_documents.append(metadata_and_text)

        return {"message": "Files processed successfully", "data": processed_documents}

    except Exception as e:
        logger.error(f"Failed to process files due to an error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
