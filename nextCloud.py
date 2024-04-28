import os
import requests
import urllib.parse 
from requests.auth import HTTPBasicAuth
from xml.etree import ElementTree

# Load environment variables
from dotenv import load_dotenv
load_dotenv()  # This loads the variables from a .env file in the same directory

# Configuration using environment variables
base_url = os.getenv('WEBDAV_URL') + '/files/' + os.getenv('WEBDAV_LOGIN') + '/'
auth = HTTPBasicAuth(os.getenv('WEBDAV_LOGIN'), os.getenv('WEBDAV_PASSWORD'))
download_dir = './data'  # Local directory to save downloaded files
# Überprüfen, ob das Verzeichnis existiert
if not os.path.exists(download_dir):
    # Wenn das Verzeichnis nicht existiert, erstellen Sie es
    os.makedirs(download_dir)

# Ensure the download directory exists
os.makedirs(download_dir, exist_ok=True)

def list_contents(url):
    """List all contents of a WebDAV directory given a URL."""
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
        print(f"Error listing contents for {url}: {response.status_code}")
        return []
    tree = ElementTree.fromstring(response.content)
    namespace = {'d': 'DAV:'}
    items = []
    for response in tree.findall('.//d:response', namespace):
        href = response.find('.//d:href', namespace).text
        resource_type = response.find('.//d:resourcetype', namespace)
        if resource_type.find('.//d:collection', namespace) is not None:
            item_type = 'directory'
        else:
            item_type = 'file'
        items.append((href, item_type))
    return items

def download_file(url, local_path):
    """Download a file from a WebDAV URL to a local path."""
    response = requests.get(url, auth=auth)
    if response.status_code == 200:
        with open(local_path, 'wb') as file:
            file.write(response.content)
    else:
        print(f"Failed to download {url}: {response.status_code}")

def recursive_download(path, local_path):
    """Recursively download contents of a directory."""
    full_url = base_url + path
    contents = list_contents(full_url)
    for href, item_type in contents:
        # Decode the URL-encoded path
        relative_path = urllib.parse.unquote(href.split('/remote.php/dav/files/' + os.getenv('WEBDAV_LOGIN') + '/')[-1])
        if item_type == 'directory':
            # Create local directory
            new_local_path = os.path.join(local_path, os.path.basename(relative_path))
            os.makedirs(new_local_path, exist_ok=True)
            # Only recursively download if the directory is not the current directory
            if relative_path != path:
                recursive_download(relative_path, new_local_path)
        elif item_type == 'file':
            file_url = base_url + relative_path
            file_local_path = os.path.join(local_path, os.path.basename(relative_path))
            download_file(file_url, file_local_path)
            print(f"Downloaded {file_local_path}")

# Start downloading from the specified path
start_path = 'Transfer Allison AI/'  # Change to your specific starting path
recursive_download(start_path, download_dir)
