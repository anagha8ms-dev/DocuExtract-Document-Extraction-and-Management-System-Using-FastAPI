
import os
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

import db_models
from database import get_db
from auth import get_current_user
from pypdf import PdfReader
from summarizer import generate_summary
from services.classifier import classify_document
from activity_logger import log_activity
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

router = APIRouter(
    prefix="/documents",
    tags=["Document Management"]
)

# Folder to store uploaded documents
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --------------------------------------------------
# 1. UPLOAD DOCUMENT
# --------------------------------------------------

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):

    allowed_extensions = [".pdf", ".jpg", ".jpeg", ".png"]

    original_filename = os.path.basename(file.filename or "")
    extension = os.path.splitext(original_filename)[1].lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, JPG, JPEG and PNG files are allowed"
        )

    unique_filename = str(uuid.uuid4()) + extension

    file_path = os.path.join(
        UPLOAD_FOLDER,
        unique_filename
    )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="File size must be 10 MB or less"
        )

    with open(file_path, "wb") as buffer:
        buffer.write(contents)

    new_document = db_models.Document(
        user_id=current_user.id,
        filename=original_filename,
        file_path=file_path,
        category="Unclassified",
        status="Uploaded"
    )

    db.add(new_document)
    db.commit()
    db.refresh(new_document)

    log_activity(
    db=db,
    user_id=current_user.id,
    document_id=new_document.id,
    filename=new_document.filename,
    action="Document Uploaded",
    status="Completed"
   )

    return {
        "message": "Document uploaded successfully",
        "document_id": new_document.id,
        "filename": new_document.filename,
        "status": new_document.status
    }


# --------------------------------------------------
# 2. EXTRACT TEXT AND CLASSIFY DOCUMENT
# --------------------------------------------------

@router.post("/{document_id}/extract")
def extract_document_text(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):

    document = db.query(db_models.Document).filter(
        db_models.Document.id == document_id,
        db_models.Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    try:
        file_extension = os.path.splitext(
            document.filename
        )[1].lower()

        # PDF Text Extraction
        if file_extension == ".pdf":

            pdf = PdfReader(document.file_path)

            extracted_text = ""

            for page in pdf.pages:
                page_text = page.extract_text()

                if page_text:
                    extracted_text += page_text + "\n"

        # Image OCR Extraction
        elif file_extension in [".jpg", ".jpeg", ".png"]:

            image = Image.open(document.file_path)

            extracted_text = pytesseract.image_to_string(
                image
            )

        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format"
            )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to extract text from this document."
        )

    # Check extracted text
    if not extracted_text.strip():

        document.status = "No Text Found"
        db.commit()

        return {
            "message": "No readable text found in this document",
            "document_id": document.id,
            "category": document.category
        }

    # Save extracted text in database
    existing_data = db.query(db_models.ExtractedData).filter(
        db_models.ExtractedData.document_id == document.id
    ).first()

    if existing_data:
        existing_data.extracted_text = extracted_text

    else:
        new_data = db_models.ExtractedData(
            document_id=document.id,
            extracted_text=extracted_text
        )

        db.add(new_data)

    # Automatically classify the document
    category = classify_document(extracted_text)

    document.category = category
    document.status = "Extracted"

    db.commit()

    # Log activity
    log_activity(
        db=db,
        user_id=current_user.id,
        document_id=document.id,
        filename=document.filename,
        action="Text Extracted",
        status="Completed"
    )

    return {
        "message": "Text extracted and classified successfully",
        "document_id": document.id,
        "filename": document.filename,
        "category": document.category,
        "status": document.status,
        "total_characters": len(extracted_text),
        "extracted_text": extracted_text
    }

# --------------------------------------------------
# 3. SUMMARIZE DOCUMENT
# --------------------------------------------------

@router.post("/{document_id}/summarize")
def summarize_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user)
):

    document = db.query(db_models.Document).filter(
        db_models.Document.id == document_id,
        db_models.Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    # Get extracted text
    extracted_data = db.query(db_models.ExtractedData).filter(
        db_models.ExtractedData.document_id == document.id
    ).first()

    if not extracted_data or not extracted_data.extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Please extract document text first"
        )

    # Generate summary
    summary_text = generate_summary(
        extracted_data.extracted_text
    )

    # Check existing summary
    existing_summary = db.query(db_models.Summary).filter(
        db_models.Summary.document_id == document.id
    ).first()

    if existing_summary:
        existing_summary.summary_text = summary_text

    else:
        new_summary = db_models.Summary(
            document_id=document.id,
            summary_text=summary_text
        )

        db.add(new_summary)

    document.status = "Summarized"
      
    log_activity(
    db=db,
    user_id=current_user.id,
    document_id=document.id,
    filename=document.filename,
    action="Summary Generated",
    status="Completed"
)
    db.commit()

    return {
        "message": "Document summarized successfully",
        "document_id": document.id,
        "category": document.category,
        "summary": summary_text,
        "status": document.status
    }
