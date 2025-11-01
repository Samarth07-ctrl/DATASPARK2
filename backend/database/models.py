# ==============================================================================
# File: backend/database/models.py
# ==============================================================================

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, DECIMAL, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    file_uploads = relationship("FileUpload", back_populates="user", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="user", cascade="all, delete-orphan")
    processing_jobs = relationship("DataProcessingJob", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    analytics = relationship("UsageAnalytics", back_populates="user")
    preferences = relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    image_dataset_jobs = relationship("ImageDatasetJob", back_populates="user", cascade="all, delete-orphan")

class UserPreferences(Base):
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    theme = Column(String(20), default="dark")
    notifications_enabled = Column(Boolean, default=True)
    auto_save_analyses = Column(Boolean, default=True)
    default_actions = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="preferences")

class FileUpload(Base):
    __tablename__ = "file_uploads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(64), unique=True, nullable=False, index=True)
    storage_path = Column(String(512)) # Crucial field for reprocessing CSVs
    row_count = Column(Integer)
    column_count = Column(Integer)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="uploaded")
    is_public = Column(Boolean, default=False)
    user = relationship("User", back_populates="file_uploads")
    analysis_results = relationship("AnalysisResult", back_populates="file_upload", cascade="all, delete-orphan")
    processing_jobs = relationship("DataProcessingJob", back_populates="file_upload", cascade="all, delete-orphan")
    analytics = relationship("UsageAnalytics", back_populates="file_upload")

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True, index=True)
    file_upload_id = Column(Integer, ForeignKey("file_uploads.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    analysis_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    file_upload = relationship("FileUpload", back_populates="analysis_results")
    user = relationship("User", back_populates="analysis_results")
    column_analyses = relationship("ColumnAnalysis", back_populates="analysis_result", cascade="all, delete-orphan")

class ColumnAnalysis(Base):
    __tablename__ = "column_analyses"
    id = Column(Integer, primary_key=True, index=True)
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id", ondelete="CASCADE"), index=True)
    column_name = Column(String(255), nullable=False)
    data_type = Column(String(50), nullable=False)
    missing_values = Column(Integer, nullable=False)
    missing_percentage = Column(DECIMAL(5,2), nullable=False)
    unique_values = Column(Integer, nullable=False)
    suggestions = Column(JSON, nullable=False)
    recommended_action = Column(String(100))
    is_problematic = Column(Boolean, default=False)
    analysis_result = relationship("AnalysisResult", back_populates="column_analyses")

class DataProcessingJob(Base):
    __tablename__ = "data_processing_jobs"
    id = Column(Integer, primary_key=True, index=True)
    file_upload_id = Column(Integer, ForeignKey("file_uploads.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    actions_applied = Column(JSON, nullable=False)
    processing_status = Column(String(20), default="pending", index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    output_filename = Column(String(255))
    file_upload = relationship("FileUpload", back_populates="processing_jobs")
    user = relationship("User", back_populates="processing_jobs")

class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_token = Column(String(255), unique=True, index=True, nullable=False)
    refresh_token = Column(String(255), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    user_agent = Column(Text)
    ip_address = Column(String(45))
    user = relationship("User", back_populates="sessions")

class UsageAnalytics(Base):
    __tablename__ = "usage_analytics"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action_type = Column(String(50), nullable=False)
    file_upload_id = Column(Integer, ForeignKey("file_uploads.id", ondelete="SET NULL"))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_details = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    user = relationship("User", back_populates="analytics")
    file_upload = relationship("FileUpload", back_populates="analytics")

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="password_reset_tokens")

class ImageDatasetJob(Base):
    __tablename__ = "image_dataset_jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_zip_filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False, unique=True) 
    image_count = Column(Integer)
    processing_status = Column(String(20), default="pending", index=True)
    actions_applied = Column(JSON)
# AFTER THE FIX

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    output_zip_path = Column(String(512))
    user = relationship("User", back_populates="image_dataset_jobs")