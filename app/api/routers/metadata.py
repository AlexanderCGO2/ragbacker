from PyPDF2 import PdfReader
from docx import Document as DocxDocument
from pptx import Presentation
import os

def extract_metadata_and_text(file_path):
    filename = os.path.basename(file_path)
    filetype = os.path.splitext(filename)[1].lower()
    title = author = None  # Default values if not found

    if filetype == '.pdf':
        try:
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                title = reader.document_info.title
                author = reader.document_info.author
                text = ' '.join([page.extract_text() for page in reader.pages if page.extract_text()])
        except Exception as e:
            logging.error(f"Error reading PDF file {filename}: {str(e)}")
            text = ""
    
    elif filetype == '.docx':
        try:
            doc = DocxDocument(file_path)
            title = doc.core_properties.title
            author = doc.core_properties.author
            text = ' '.join([para.text for para in doc.paragraphs if para.text])
        except Exception as e:
            logging.error(f"Error reading DOCX file {filename}: {str(e)}")
            text = ""

    elif filetype == '.pptx':
        try:
            pres = Presentation(file_path)
            title = pres.core_properties.title
            author = pres.core_properties.author
            text = ' '.join([slide.notes_slide.notes_text_frame.text for slide in pres.slides if slide.has_notes_slide and slide.notes_slide.notes_text_frame])
        except Exception as e:
            logging.error(f"Error reading PPTX file {filename}: {str(e)}")
            text = ""

    else:
        logging.warning(f"Unsupported file type {filetype} for file {filename}")
        text = ""

    return {
        "filename": filename,
        "title": title if title else "Unknown",
        "author": author if author else "Unknown",
        "filetype": filetype,
        "text": text
    }
