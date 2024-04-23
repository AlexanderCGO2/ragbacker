from dotenv import load_dotenv
import os
import logging
from llama_index.core.storage import StorageContext
from llama_index.core.indices import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from app.settings import init_settings
from app.engine.loaders import get_documents
import requests
from pydantic import BaseModel
from typing import List, Any, Optional, Dict, Tuple
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from llama_index.core.chat_engine.types import (
    BaseChatEngine,
)
from llama_index.core.schema import NodeWithScore
from llama_index.core.llms import ChatMessage, MessageRole
from app.engine import get_chat_engine

#loggig.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


ingest_router = r = APIRouter()

@r.post("")
async def ingest():
    try:
        load_dotenv()
        init_settings()
        generate_datasource()
        return {"message": "Ingestio started successfully"}   
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def generate_datasource():
    logger.info("Creating new index")
    documents = get_documents()
    try:
        store = PineconeVectorStore(
            api_key=os.environ["PINECONE_API_KEY"],
            index_name=os.environ["PINECONE_INDEX_NAME"],
            environment=os.environ["PINECONE_ENVIRONMENT"],
        )
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 404:
            logger.error("HTTP 404 Error: The requested resource could not be found.")
            return
        else:
            raise
    storage_context = StorageContext.from_defaults(vector_store=store)
    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )
    logger.info(
        f"Successfully created embeddings and save to your Pinecone index {os.environ['PINECONE_INDEX_NAME']}"
    )