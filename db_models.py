from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100),unique= True, nullable=False)
    email = Column(String(150),unique= True, nullable=False)
    password = Column(String(255), nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    category = Column(String(100), default="Unclassified")
    status = Column(String(50), default= "Uploaded")

class ExtractedData(Base):
    __tablename__ = "extracted_data"


    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), unique=True)
    extracted_text = Column(Text)

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), unique=True)
    summary_text = Column(Text)




class ProcessingActivity(Base):
    __tablename__ = "processing_activities"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False
    )

    filename = Column(String(255), nullable=False)

    action = Column(String(100), nullable=False)

    status = Column(String(50), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    