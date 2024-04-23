import os
from dotenv import load_dotenv
from webdav3.client import Client

# Laden Sie die Umgebungsvariablen aus der .env-Datei
load_dotenv()

def download_webdav_files():
    # Konfigurieren Sie den WebDAV-Client
    webdav_url = os.getenv('WEBDAV_URL')
    webdav_login = os.getenv('WEBDAV_LOGIN')
    webdav_password = os.getenv('WEBDAV_PASSWORD')

    if not webdav_url or not webdav_login or not webdav_password:
        raise ValueError("WEBDAV_URL, WEBDAV_LOGIN and WEBDAV_PASSWORD environment variables must be set")

    options = {
        'webdav_hostname': webdav_url,
        'webdav_login':    webdav_login,
        'webdav_password': webdav_password,
        'webdav_override_methods': {
            'list': 'GET'
        }
    }
    client = Client(options)

    # Stellen Sie sicher, dass das lokale Verzeichnis existiert
    local_dir = 'temp_data'
    os.makedirs(local_dir, exist_ok=True)

    # Liste alle Dateien im Wurzelverzeichnis des WebDAV-Servers
    files = client.list('/')
    print(files)
    # Lade jede Datei herunter
    for file in files:
        local_file_path = os.path.join(local_dir, os.path.basename(file))
        client.download_sync(remote_path=file, local_path=local_file_path)

# Aufruf der Funktion
download_webdav_files()