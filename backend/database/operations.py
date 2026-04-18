# ==============================================================================
# File: backend/database/operations.py
# ==============================================================================

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import logging
import json

# Import all models from the models.py file
from .models import (
    FileUpload, AnalysisResult, ColumnAnalysis, DataProcessingJob, 
    UsageAnalytics, ImageDatasetJob, User
)

logger = logging.getLogger(__name__)

class DatabaseOperations:
    
    @staticmethod
    def create_file_upload(db: Session, original_filename: str, file_content: bytes, 
                             user_id: Optional[int] = None, 
                             storage_path: Optional[str] = None) -> FileUpload:
        """
        Create a new file upload record.
        Checks for existing file hash for this user to avoid duplicates.
        """
        try:
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            # Check if this user has already uploaded this exact file
            query = db.query(FileUpload).filter(
                FileUpload.file_hash == file_hash,
                FileUpload.user_id == user_id
            )
            
            existing_file = query.first()
            
            if existing_file:
                # If file exists, update its storage path (if new one is provided)
                # and return the existing record.
                if storage_path and not existing_file.storage_path:
                    existing_file.storage_path = storage_path
                    db.commit()
                logger.info(f"File with hash {file_hash} already exists for user {user_id}. Returning existing record.")
                return existing_file
            
            # If file doesn't exist for this user, create a new record
            file_upload = FileUpload(
                user_id=user_id,
                filename=original_filename, # Use original_filename for both
                original_filename=original_filename,
                file_size=len(file_content),
                file_hash=file_hash,
                storage_path=storage_path
            )
            db.add(file_upload)
            db.commit()
            db.refresh(file_upload)
            return file_upload
        except Exception as e:
            logger.error(f"Error creating file upload: {e}")
            db.rollback()
            raise

    @staticmethod
    def save_analysis_result(db: Session, file_upload_id: int, 
                             analysis_data: Dict[str, Any], user_id: Optional[int] = None) -> AnalysisResult:
        """Save analysis results to database, including AI insights."""
        try:
            # Check if an analysis result for this file already exists
            existing_analysis = db.query(AnalysisResult).filter(
                AnalysisResult.file_upload_id == file_upload_id
            ).first()

            if existing_analysis:
                # If it exists, delete its old column_analyses before adding new ones
                db.query(ColumnAnalysis).filter(
                    ColumnAnalysis.analysis_result_id == existing_analysis.id
                ).delete(synchronize_session=False)
                
                # Update the main analysis data
                existing_analysis.analysis_data = analysis_data
                existing_analysis.created_at = datetime.utcnow() # Update timestamp
                analysis_result = existing_analysis
                db.flush() # Ensure analysis_result.id is available
            else:
                # Create a new analysis result
                analysis_result = AnalysisResult(
                    file_upload_id=file_upload_id,
                    user_id=user_id,
                    analysis_data=analysis_data
                )
                db.add(analysis_result)
                db.flush() # Get the new analysis_result.id
            
            # Add the new column_analyses records
            for col_analysis in analysis_data.get('column_analysis', []):
                column_analysis = ColumnAnalysis(
                    analysis_result_id=analysis_result.id,
                    column_name=col_analysis['column_name'],
                    data_type=col_analysis['data_type'],
                    missing_values=col_analysis['missing_values'],
                    missing_percentage=float(col_analysis['missing_percentage']),
                    unique_values=col_analysis['unique_values'],
                    suggestions=json.dumps(col_analysis['suggestions']), # Store as JSON string
                    recommended_action=col_analysis.get('recommended_action'),
                    is_problematic=col_analysis.get('is_problematic', False),
                    
                    # --- ADDED THESE NEW FIELDS TO BE SAVED ---
                    ai_insights=col_analysis.get('ai_insights'),
                    ai_recommendation=col_analysis.get('ai_recommendation')
                    # --- END OF NEW FIELDS ---
                )
                db.add(column_analysis)
            
            # Update the FileUpload record with row/column counts
            file_upload = db.query(FileUpload).filter(FileUpload.id == file_upload_id).first()
            if file_upload:
                file_upload.row_count = analysis_data.get('row_count')
                file_upload.column_count = analysis_data.get('column_count')
                file_upload.status = 'analyzed'
            
            db.commit()
            db.refresh(analysis_result)
            return analysis_result
        except Exception as e:
            logger.error(f"Error saving analysis result: {e}")
            db.rollback()
            raise

    @staticmethod
    def create_processing_job(db: Session, file_upload_id: int, user_id: int, 
                              actions: List[Dict[str, Any]]) -> DataProcessingJob:
        """Create a new data processing job for a CSV file."""
        try:
            processing_job = DataProcessingJob(
                file_upload_id=file_upload_id,
                user_id=user_id,
                actions_applied=actions,
                processing_status='pending'
            )
            db.add(processing_job)
            db.commit()
            db.refresh(processing_job)
            return processing_job
        except Exception as e:
            logger.error(f"Error creating CSV processing job: {e}")
            db.rollback()
            raise

    @staticmethod
    def update_processing_job_status(db: Session, job_id: int, status: str, 
                                     error_message: Optional[str] = None,
                                     output_filename: Optional[str] = None):
        """Update CSV processing job status"""
        try:
            job = db.query(DataProcessingJob).filter(DataProcessingJob.id == job_id).first()
            if job:
                job.processing_status = status
                if status == 'completed':
                    job.completed_at = datetime.utcnow()
                if error_message:
                    job.error_message = error_message
                if output_filename:
                    job.output_filename = output_filename
                db.commit()
        except Exception as e:
            logger.error(f"Error updating CSV processing job status: {e}")
            db.rollback()
            raise

    @staticmethod
    def create_image_dataset_job(db: Session, user_id: int, filename: str, 
                                 storage_path: str, image_count: int) -> ImageDatasetJob:
        """Create a new image dataset job record in the database."""
        try:
            job = ImageDatasetJob(
                user_id=user_id,
                original_zip_filename=filename,
                storage_path=storage_path,
                image_count=image_count,
                processing_status="analyzed"
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job
        except Exception as e:
            logger.error(f"Error creating image dataset job: {e}")
            db.rollback()
            raise

    @staticmethod
    def get_user_upload_history(db: Session, user_id: int, limit: int = 50) -> List[FileUpload]:
        """Get specific user's upload history"""
        try:
            return db.query(FileUpload).filter(FileUpload.user_id == user_id).order_by(desc(FileUpload.upload_timestamp)).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting user upload history: {e}")
            return []

    @staticmethod
    def get_usage_statistics(db: Session, days: int = 30, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get usage statistics for the last N days"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            upload_query = db.query(func.count(FileUpload.id)).filter(FileUpload.upload_timestamp >= start_date)
            job_query = db.query(func.count(DataProcessingJob.id)).filter(DataProcessingJob.started_at >= start_date)
            if user_id:
                upload_query = upload_query.filter(FileUpload.user_id == user_id)
                job_query = job_query.filter(DataProcessingJob.user_id == user_id)
            total_uploads = upload_query.scalar() or 0
            total_jobs = job_query.scalar() or 0
            successful_query = db.query(func.count(DataProcessingJob.id)).filter(and_(DataProcessingJob.started_at >= start_date, DataProcessingJob.processing_status == 'completed'))
            if user_id:
                successful_query = successful_query.filter(DataProcessingJob.user_id == user_id)
            successful_jobs = successful_query.scalar() or 0
            success_rate = (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0
            return {'total_uploads': total_uploads, 'total_processing_jobs': total_jobs, 'success_rate': round(success_rate, 2)}
        except Exception as e:
            logger.error(f"Error getting usage statistics: {e}")
            return {'total_uploads': 0, 'total_processing_jobs': 0, 'success_rate': 0}