from dotenv import load_dotenv

load_dotenv()

import os
import mimetypes
import logging
from llama_index.core.storage import StorageContext
from llama_index.core.indices import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from app.settings import init_settings
from app.engine.loaders import get_documents
import firebase_admin
import base64
from firebase_admin import credentials, firestore

from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.extractors import TitleExtractor, SummaryExtractor
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import MetadataMode


def build_pipeline():
    llm = OpenAI(model="gpt-3.5-turbo", temperature=0.1)

    transformations = [
        SentenceSplitter(chunk_size=1024, chunk_overlap=20),
        TitleExtractor(
            llm=llm, metadata_mode=MetadataMode.EMBED, num_workers=8
        ),
        SummaryExtractor(
            llm=llm, metadata_mode=MetadataMode.EMBED, num_workers=8
        ),
        OpenAIEmbedding(),
    ]

    return IngestionPipeline(transformations=transformations)




logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

encoded_key = os.getenv('FIREBASE_PRIVATE_KEY_BASE64')

# Decode the Base64 string
decoded_key = base64.b64decode(encoded_key).decode('utf-8')
firebase_config = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": decoded_key, # Properly format the private key
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
}
#  Initialize Firebase Admin with the constructed configuration
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred)
# Initialize Firebase
db = firestore.client()

def generate_datasource():
    logger.info("Creating new index")
    # load the documents and create the index
    documents = get_documents()
  

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
    logger.info(
        f"Successfully created embeddings and save to your Pinecone index {os.environ['PINECONE_INDEX_NAME']}"
    )
      # Dokumentnamen in Firebase speichern
    # Dokumentnamen und Dateinamen in Firebase speichern
   

    doc_ref = db.collection('ingestedDocs')

    for doc in documents:
        if 'file_name' in doc.metadata and 'file_type' in doc.metadata:
            filename = os.path.basename(doc.metadata['file_name'])
            filetype = mimetypes.guess_extension(doc.metadata['file_type'])
            doc_ref.add({'filename': filename, 'filetype': filetype})  # Ein neues Dokument für jeden Dateinamen und Dateityp erstellen

    logger.info("Document names, filenames, and filetypes saved to Firebase")


if __name__ == "__main__":
    init_settings()
    generate_datasource()
