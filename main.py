import os
import uuid
from fastapi import FastAPI
from db_models import Base
from database import engine
from routers import users, documents
from fastapi import FastAPI, Request, Form, Depends, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse

import db_models
from database import get_db
from auth import hash_password , verify_password, create_access_token, SECRET_KEY, ALGORITHM
import jwt

from pypdf import PdfReader
from services.classifier import classify_document
from summarizer import generate_summary
from sqlalchemy import desc

import pytesseract
from PIL import Image
from pypdf import PdfReader
from activity_logger import log_activity


app = FastAPI(
    title="DocuExtract",
    description="AI Powered Document Processing System",
    version="1.0.0"
)

# Create database tables
Base.metadata.create_all(bind=engine)

app.include_router(users.router)

app.include_router(documents.router)

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# @app.get("/")
# def home():
#     return {"message": "Welcome to DocuExtract API"}

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

templates = Jinja2Templates(
    directory="templates"
)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={}
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={}
    )


@app.post("/register", response_class=HTMLResponse)
def register_frontend(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    # Check existing username
    existing_user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()

    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Username already exists"}
        )

    # Check existing email
    existing_email = db.query(db_models.User).filter(
        db_models.User.email == email
    ).first()

    if existing_email:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Email already exists"}
        )

    # Hash password
    hashed_password = hash_password(password)

    # Create new user
    new_user = db_models.User(
        username=username,
        email=email,
        password=hashed_password
    )

    db.add(new_user)
    db.commit()

    return RedirectResponse(
        url="/login",
        status_code=303
    )



@app.post("/login")
def frontend_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()

    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid username or password"}
        )

    token = create_access_token(
        {"sub": user.username}
    )

    response = RedirectResponse(
        url="/dashboard",
        status_code=303
    )

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=1800
    )

    return response


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session= Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if not username:
            raise ValueError("Invalid token")

    except Exception:
        response = RedirectResponse(
            url="/login",
            status_code=303
        )
        response.delete_cookie("access_token")
        return response

    user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()



    # Total documents uploaded by this user
    total_documents = db.query(db_models.Document).filter(
        db_models.Document.user_id == user.id
    ).count()

    # Successfully extracted or summarized documents
    processed_documents = db.query(db_models.Document).filter(
        db_models.Document.user_id == user.id,
        db_models.Document.status.in_(["Extracted", "Summarized"])
    ).count()

    # Documents waiting for processing
    pending_documents = db.query(db_models.Document).filter(
        db_models.Document.user_id == user.id,
        db_models.Document.status == "Uploaded"
    ).count()


    if not user:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "username": user.username,
            "total_documents": total_documents,
            "processed_documents": processed_documents,
            "pending_documents": pending_documents
            }
    )


# -----------------------------------------
# UPLOAD DOCUMENT PAGE
# -----------------------------------------

@app.get("/upload-page", response_class=HTMLResponse)
def upload_page(request: Request):

    token = request.cookies.get("access_token")

    if not token:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if not username:
            raise ValueError("Invalid token")

    except Exception:
        response = RedirectResponse(
            url="/login",
            status_code=303
        )
        response.delete_cookie("access_token")
        return response

    return templates.TemplateResponse(
        request=request,
        name="upload.html",
        context={}
    )


# -----------------------------------------
# PROCESS DOCUMENT UPLOAD
# -----------------------------------------

@app.post("/upload-page", response_class=HTMLResponse)
async def upload_document_frontend(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    token = request.cookies.get("access_token")

    if not token:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if not username:
            raise ValueError("Invalid token")

    except Exception:
        response = RedirectResponse(
            url="/login",
            status_code=303
        )
        response.delete_cookie("access_token")
        return response

    user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # Validate file extension
    original_filename = os.path.basename(file.filename or "")
    extension = os.path.splitext(original_filename)[1].lower()

    allowed_extensions = [".pdf", ".jpg", ".jpeg", ".png"]

    if extension not in allowed_extensions:
        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context={"error": "Only PDF, JPG, JPEG and PNG files are allowed"}
        )

    # Read file
    contents = await file.read()

    if not contents:
        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context={"error": "Please select a file"}
        )

    if len(contents) > 10 * 1024 * 1024:
        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context={"error": "File size must be 10 MB or less"}
        )

    # Save file
    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)

    unique_filename = str(uuid.uuid4()) + extension

    file_path = os.path.join(
        upload_folder,
        unique_filename
    )

    with open(file_path, "wb") as buffer:
        buffer.write(contents)

    # Save document details in MySQL
    new_document = db_models.Document(
        user_id=user.id,
        filename=original_filename,
        file_path=file_path,
        category="Unclassified",
        status="Uploaded"
    )

    try:
        db.add(new_document)
        db.commit()
        db.refresh(new_document)

    except Exception:
        db.rollback()

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=500,
            detail="Unable to save document"
        )

    return templates.TemplateResponse(
        request=request,
        name="upload.html",
        context={
            "message": "Document uploaded successfully!",
            "filename": original_filename,
            "document_id": new_document.id
        }
    )



# -----------------------------------------
# MY DOCUMENTS PAGE
# -----------------------------------------

@app.get("/documents-page", response_class=HTMLResponse)
def my_documents(
    request: Request,
    db: Session = Depends(get_db),
    message: str = None
):

    token = request.cookies.get("access_token")

    if not token:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if not username:
            raise ValueError("Invalid token")

    except Exception:
        response = RedirectResponse(
            url="/login",
            status_code=303
        )
        response.delete_cookie("access_token")
        return response

    user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    documents = db.query(db_models.Document).filter(
        db_models.Document.user_id == user.id
    ).order_by(
        db_models.Document.id.desc()
    ).all()

    document_list = []

    for document in documents:

        extracted_data = db.query(
            db_models.ExtractedData
        ).filter(
            db_models.ExtractedData.document_id == document.id
        ).first()

        summary_data = db.query(
            db_models.Summary
        ).filter(
            db_models.Summary.document_id == document.id
        ).first()

        document_list.append({
            "id": document.id,
            "filename": document.filename,
            "category": document.category,
            "status": document.status,
            "is_pdf" : document.filename.lower().endswith(".pdf"),
            "has_extracted_text": (
                extracted_data is not None
                and bool(extracted_data.extracted_text)
            ),
            "has_summary": (
                summary_data is not None
                and bool(summary_data.summary_text)
            )
        })

    return templates.TemplateResponse(
        request=request,
        name="my_documents.html",
        context={
            "username": user.username,
            "documents": document_list,
            "message": message
        }
    )



# -----------------------------------------
# EXTRACT TEXT FROM MY DOCUMENTS PAGE
# -----------------------------------------

@app.post("/documents-page/{document_id}/extract")
def extract_document_frontend(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    # Check login
    token = request.cookies.get("access_token")

    if not token:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if not username:
            raise ValueError("Invalid token")

    except Exception:
        response = RedirectResponse(
            url="/login",
            status_code=303
        )
        response.delete_cookie("access_token")
        return response

    # Get user
    user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # Get document belonging to this user
    document = db.query(db_models.Document).filter(
        db_models.Document.id == document_id,
        db_models.Document.user_id == user.id
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
            detail="Unable to extract text from this document"
        )

    # Check extracted text
    if not extracted_text.strip():

        document.status = "No Text Found"
        db.commit()

        log_activity(
            db=db,
            user_id=user.id,
            document_id=document.id,
            filename=document.filename,
            action="Text Extraction",
            status="No Text Found"
        )

        return RedirectResponse(
            url="/documents-page?message=No readable text found",
            status_code=303
        )

    # Save extracted text
    existing_data = db.query(
        db_models.ExtractedData
    ).filter(
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

    # Automatic classification
    category = classify_document(extracted_text)

    document.category = category
    document.status = "Extracted"

    db.commit()

    # Activity logging
    log_activity(
        db=db,
        user_id=user.id,
        document_id=document.id,
        filename=document.filename,
        action="Text Extracted",
        status="Completed"
    )

    return RedirectResponse(
        url="/documents-page?message=Text extracted successfully",
        status_code=303
    )

# -----------------------------------------
# GENERATE SUMMARY FROM MY DOCUMENTS PAGE
# -----------------------------------------

@app.post("/documents-page/{document_id}/summarize")
def summarize_document_frontend(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    # Check login
    token = request.cookies.get("access_token")

    if not token:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if not username:
            raise ValueError("Invalid token")

    except Exception:
        response = RedirectResponse(
            url="/login",
            status_code=303
        )
        response.delete_cookie("access_token")
        return response

    # Get logged-in user
    user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    # Check document ownership
    document = db.query(db_models.Document).filter(
        db_models.Document.id == document_id,
        db_models.Document.user_id == user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    # Get extracted text
    extracted_data = db.query(
        db_models.ExtractedData
    ).filter(
        db_models.ExtractedData.document_id == document.id
    ).first()

    if not extracted_data or not extracted_data.extracted_text.strip():
        return RedirectResponse(
            url="/documents-page?message=Please extract text first",
            status_code=303
        )

    try:
        # Generate summary
        summary_text = generate_summary(
            extracted_data.extracted_text
        )

        if not summary_text:
            raise ValueError("Summary generation returned empty text")

        # Check existing summary
        existing_summary = db.query(
            db_models.Summary
        ).filter(
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

        db.commit()

    except Exception:
        db.rollback()

        return RedirectResponse(
            url="/documents-page?message=Unable to generate summary",
            status_code=303
        )

    return RedirectResponse(
        url="/documents-page?message=Summary generated successfully",
        status_code=303
    )



# -----------------------------------------
# VIEW DOCUMENT SUMMARY
# -----------------------------------------

@app.get(
    "/documents-page/{document_id}/summary",
    response_class=HTMLResponse
)
def view_document_summary(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    # Check login
    token = request.cookies.get("access_token")

    if not token:
        return RedirectResponse("/login", status_code=303)

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if not username:
            raise ValueError("Invalid token")

    except Exception:
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("access_token")
        return response

    # Get user
    user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()

    if not user:
        return RedirectResponse("/login", status_code=303)

    # Check document ownership
    document = db.query(db_models.Document).filter(
        db_models.Document.id == document_id,
        db_models.Document.user_id == user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    # Get summary from database
    summary_data = db.query(db_models.Summary).filter(
        db_models.Summary.document_id == document.id
    ).first()

    if not summary_data:
        raise HTTPException(
            status_code=404,
            detail="Summary not found. Generate summary first."
        )

    return templates.TemplateResponse(
        request=request,
        name="view_summary.html",
        context={
            "username": user.username,
            "document": document,
            "summary": summary_data.summary_text
        }
    )


# -----------------------------------------
# VIEW EXTRACTED TEXT
# -----------------------------------------

@app.get(
    "/documents-page/{document_id}/extracted-text",
    response_class=HTMLResponse
)
def view_extracted_text(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    # Check login
    token = request.cookies.get("access_token")

    if not token:
        return RedirectResponse("/login", status_code=303)

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if not username:
            raise ValueError("Invalid token")

    except Exception:
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("access_token")
        return response

    # Get logged-in user
    user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()

    if not user:
        return RedirectResponse("/login", status_code=303)

    # Check document ownership
    document = db.query(db_models.Document).filter(
        db_models.Document.id == document_id,
        db_models.Document.user_id == user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    # Get extracted text
    extracted_data = db.query(
        db_models.ExtractedData
    ).filter(
        db_models.ExtractedData.document_id == document.id
    ).first()

    if not extracted_data:
        raise HTTPException(
            status_code=404,
            detail="Extracted text not found"
        )

    return templates.TemplateResponse(
        request=request,
        name="view_extracted_text.html",
        context={
            "username": user.username,
            "document": document,
            "extracted_text": extracted_data.extracted_text
        }
    )

@app.get("/processing-history", response_class=HTMLResponse)
def processing_history(
    request: Request,
    db: Session = Depends(get_db)
):

    token = request.cookies.get("access_token")

    if not token:
        return RedirectResponse("/login")

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

    except jwt.InvalidTokenError:
        return RedirectResponse("/login")

    user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()

    if not user:
        return RedirectResponse("/login")

    activities = db.query(
        db_models.ProcessingActivity
    ).filter(
        db_models.ProcessingActivity.user_id == user.id
    ).order_by(
        desc(db_models.ProcessingActivity.created_at)
    ).all()

    total_activities = len(activities)

    extraction_count = sum(
        1 for a in activities
        if a.action == "Text Extracted"
    )

    summary_count = sum(
        1 for a in activities
        if a.action == "Summary Generated"
    )

    return templates.TemplateResponse(
        request=request,
        name="processing_history.html",
        context={
            "username": user.username,
            "activities": activities,
            "total_activities": total_activities,
            "extraction_count": extraction_count,
            "summary_count": summary_count
        }
    )


@app.get("/logout")
def logout():
    response = RedirectResponse(
        url="/login",
        status_code=303
    )

    response.delete_cookie("access_token")

    return response
