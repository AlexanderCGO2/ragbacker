from dotenv import load_dotenv

load_dotenv()

import logging
import os
import uvicorn
from fastapi import FastAPI, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.api.routers.chat import chat_router
from app.api.routers.ingest import ingest_router
from app.api.routers.metadata import extract_metadata_and_text
from app.settings import init_settings
from requests.auth import HTTPBasicAuth
from xml.etree import ElementTree
import requests
import urllib.parse
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


init_settings()

environment = os.getenv("ENVIRONMENT", "dev")  # Default to 'development' if not set
load_dotenv()  # This loads the variables from a .env file in the same directory

# Configuration using environment variables 
base_url = os.getenv('WEBDAV_URL') + '/files/' + os.getenv('WEBDAV_LOGIN') + '/'
auth = HTTPBasicAuth(os.getenv('WEBDAV_LOGIN'), os.getenv('WEBDAV_PASSWORD'))



# Redirect to documentation page when accessing base URL
@app.get("/")
async def redirect_to_docs():
    return RedirectResponse(url="/docs")

app.include_router(ingest_router, prefix="/api/ingest")

app.include_router(chat_router, prefix="/api/chat")
def list_contents(directory):
    """List all contents of a WebDAV directory given a directory path."""
    url = base_url + urllib.parse.quote(directory)
    headers = {
        "Depth": "1",  # Depth: 1 to list direct children only
        "Content-Type": "application/xml"
    }
    propfind_body = '''
    <d:propfind xmlns:d="DAV:">
    <d:prop>
        <d:resourcetype/>
        <d:getcontenttype/>
    </d:prop>
    </d:propfind>
    '''
    response = requests.request("PROPFIND", url, headers=headers, data=propfind_body, auth=auth)
    if response.status_code != 207:
        return {"error": f"Error listing contents for {url}: {response.status_code}"}
    tree = ElementTree.fromstring(response.content)
    namespace = {'d': 'DAV:'}
    items = []
    for response in tree.findall('.//d:response', namespace):
        href = response.find('.//d:href', namespace).text
        resource_type = response.find('.//d:resourcetype', namespace)
        item_type = 'directory' if resource_type.find('.//d:collection', namespace) is not None else 'file'
        items.append({"href": href, "type": item_type})
    return items

@app.get("/files/{directory:path}")
async def read_files(directory: str = Path(..., description="The directory to list contents from")):
        """Endpoint to list files in a given directory of the WebDAV server."""
        return list_contents(directory)


if __name__ == "__main__":
    app_host = os.getenv("APP_HOST", "0.0.0.0")
    app_port = int(os.getenv("APP_PORT", "8000"))
    reload = True if environment == "dev" else False

    uvicorn.run(app="main:app", host=app_host, port=app_port, reload=reload)
