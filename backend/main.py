# ==============================================================================
# File: backend/main.py
# ==============================================================================

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks, Request, status, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import List, Dict, Any, Optional
import pandas as pd
from io import StringIO, BytesIO
from starlette.responses import StreamingResponse
import numpy as np
import logging
from sqlalchemy.orm import Session
from datetime import datetime
import zipfile
from PIL import Image, ImageFilter, ImageEnhance
from uuid import uuid4
import os
from database.config import get_db, check_database_connection, init_database 
from database.operations import DatabaseOperations
from database.auth_operations import AuthOperations
from database.models import User as UserModel, ImageDatasetJob, FileUpload
from sklearn.impute import KNNImputer
from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder, OneHotEncoder
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer

logger = logging.getLogger(__name__)

app = FastAPI(
    title="DataSpark AI Preprocessing API (v6 - With Image Processing)",
    description="An intelligent API for analyzing and cleaning CSV and Image datasets.",
    version="6.0.0",
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting FastAPI application startup event...")
    if init_database():
        logger.info("Database tables created/checked successfully during startup.")
    else:
        logger.error("Failed to initialize database tables during startup. Exiting.")
        raise RuntimeError("Database initialization failed.")
    
    if not check_database_connection():
        logger.critical("Database connection failed after initialization!")
        raise RuntimeError("Database connection check failed on startup.")
    logger.info("FastAPI application startup event complete.")

security = HTTPBearer()

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserLogin(BaseModel):
    username_or_email: str
    password: str

# AFTER THE FIX

from pydantic import BaseModel, EmailStr, ConfigDict # Make sure ConfigDict is imported at the top

# AFTER THE FIX

# Make sure ConfigDict is imported at the top of the file with your other pydantic imports
from pydantic import BaseModel, EmailStr, ConfigDict 

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    # This line is the fix for Pydantic v2 compatibility
    model_config = ConfigDict(from_attributes=True)

class LoginResponse(BaseModel):
    user: UserResponse
    session_token: str
    refresh_token: str
    expires_at: str

class ColumnAnalysis(BaseModel):
    column_name: str
    data_type: str
    missing_values: int
    missing_percentage: float
    unique_values: int
    suggestions: List[str] = []
    recommended_action: Optional[str] = None
    is_problematic: bool = False

class AnalysisResponse(BaseModel):
    filename: str
    row_count: int
    column_count: int
    column_analysis: List[ColumnAnalysis]
    file_id: Optional[int] = None

class Action(BaseModel):
    column: str
    action: str
    value: Optional[Any] = None

class ProcessRequest(BaseModel):
    actions: List[Action]
    file_id: int

class ImageAnalysisSummary(BaseModel):
    job_id: int
    filename: str
    image_count: int
    formats: Dict[str, int]
    dimensions: Dict[str, int]
    modes: Dict[str, int]

class ImageProcessAction(BaseModel):
    action: str
    params: Optional[Dict[str, Any]] = None

class ImageProcessRequest(BaseModel):
    job_id: int
    actions: List[ImageProcessAction]

UPLOAD_DIR_CSV = "uploaded_csv_files"
UPLOAD_DIR_IMAGES = "uploaded_image_datasets"
os.makedirs(UPLOAD_DIR_CSV, exist_ok=True)
os.makedirs(UPLOAD_DIR_IMAGES, exist_ok=True)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), 
                           db: Session = Depends(get_db)) -> UserModel:
    session_token = credentials.credentials
    user = AuthOperations.get_user_by_session_token(db, session_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def analyze_column(df: pd.DataFrame, column_name: str) -> ColumnAnalysis:
    try:
        col = df[column_name]
        data_type = str(col.dtype)
        missing_values = int(col.isnull().sum())
        total_rows = len(df)
        missing_percentage = round((missing_values / total_rows) * 100, 2) if total_rows > 0 else 0
        unique_values = int(col.nunique())
        suggestions = ["drop_column"]
        recommended_action = None
        is_problematic = False
        if missing_values > 0:
            is_problematic = True
            suggestions.append("drop_missing_rows")
            if np.issubdtype(col.dtype, np.number):
                try:
                    skewness = col.skew()
                    recommended_action = "impute_median" if abs(skewness) > 1 else "impute_mean"
                except Exception:
                    recommended_action = "impute_mean"
                suggestions.extend(["impute_mean", "impute_median", "impute_knn", "impute_iterative"])
            else:
                recommended_action = "impute_mode"
                suggestions.append("impute_mode")
        if data_type == 'object':
            suggestions.extend(["to_lowercase", "to_uppercase", "trim_whitespace", "remove_special_characters", "convert_to_datetime", "convert_to_numeric"])
            if 1 < unique_values <= 50:
                suggestions.extend(["one_hot_encode", "label_encode"])
                if not recommended_action: recommended_action = "one_hot_encode"
        if np.issubdtype(col.dtype, np.number):
             suggestions.extend(["scale_standard", "scale_minmax", "transform_log", "handle_outliers_iqr"])
        if 'datetime' in data_type:
            suggestions.extend(['extract_year', 'extract_month', 'extract_day', 'extract_day_of_week'])
        return ColumnAnalysis(column_name=column_name, data_type=data_type, missing_values=missing_values, missing_percentage=missing_percentage, unique_values=unique_values, suggestions=list(dict.fromkeys(suggestions)), recommended_action=recommended_action, is_problematic=is_problematic)
    except Exception as e:
        logger.error(f"Error analyzing column '{column_name}': {e}")
        return ColumnAnalysis(column_name=column_name, data_type="unknown", missing_values=0, missing_percentage=0, unique_values=0, suggestions=["drop_column"], recommended_action="drop_column", is_problematic=True)

@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    try:
        user = AuthOperations.create_user(db=db, username=user_data.username, email=user_data.email, password=user_data.password, first_name=user_data.first_name, last_name=user_data.last_name)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed")

@app.post("/auth/login")
async def login_user(login_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    try:
        user = AuthOperations.authenticate_user(db=db, username_or_email=login_data.username_or_email, password=login_data.password)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        session = AuthOperations.create_session(db=db, user_id=user.id, user_agent=request.headers.get("User-Agent"), ip_address=request.client.host)
        response_data = { "user": { "id": user.id, "username": user.username, "email": user.email, "first_name": user.first_name, "last_name": user.last_name }, "session_token": session.session_token, "refresh_token": session.refresh_token, "expires_at": session.expires_at.isoformat() }
        return JSONResponse(content=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during login: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal server error occurred during login.")

@app.post("/auth/logout")
async def logout_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    success = AuthOperations.logout_user(db, credentials.credentials)
    if success:
        return {"message": "Successfully logged out"}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Logout failed")

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserModel = Depends(get_current_user)):
    return current_user

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...), current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    storage_path = os.path.join(UPLOAD_DIR_CSV, f"{uuid4().hex}_{file.filename}")
    with open(storage_path, "wb") as f:
        f.write(contents)
    db_file_upload = DatabaseOperations.create_file_upload(db, file.filename, contents, current_user.id, storage_path)
    try:
        content_str = contents.decode('utf-8')
    except UnicodeDecodeError:
        content_str = contents.decode('latin-1')
    df = pd.read_csv(StringIO(content_str))
    if df.empty:
        raise HTTPException(status_code=400, detail="CSV file is empty or could not be parsed")
    row_count, col_count = df.shape
    analysis_results = [analyze_column(df, col) for col in df.columns]
    response_data = {"filename": file.filename, "row_count": row_count, "column_count": col_count, "column_analysis": [ar.dict() for ar in analysis_results]}
    background_tasks.add_task(DatabaseOperations.save_analysis_result, db, db_file_upload.id, response_data, current_user.id)
    return AnalysisResponse(**response_data, file_id=db_file_upload.id)

@app.post("/process")
async def process_data(request: ProcessRequest, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    job_id = None
    try:
        file_record = db.query(FileUpload).filter(FileUpload.id == request.file_id, FileUpload.user_id == current_user.id).first()
        if not file_record or not file_record.storage_path:
            raise HTTPException(status_code=404, detail="Original file not found or path is missing.")
        actions_for_db = [action.dict() for action in request.actions]
        db_job = DatabaseOperations.create_processing_job(db=db, file_upload_id=request.file_id, user_id=current_user.id, actions=actions_for_db)
        job_id = db_job.id
        df = pd.read_csv(file_record.storage_path)
        processed_df = df.copy()
        for action_item in request.actions:
            column = action_item.column
            action_type = action_item.action
            if column not in processed_df.columns: continue
            if action_type == "drop_column": processed_df.drop(columns=[column], inplace=True)
            elif action_type == "drop_missing_rows": processed_df.dropna(subset=[column], inplace=True)
            elif action_type == "impute_mean" and np.issubdtype(processed_df[column].dtype, np.number): processed_df[column].fillna(processed_df[column].mean(), inplace=True)
            elif action_type == "impute_median" and np.issubdtype(processed_df[column].dtype, np.number): processed_df[column].fillna(processed_df[column].median(), inplace=True)
            elif action_type == "impute_mode": processed_df[column].fillna(processed_df[column].mode()[0], inplace=True)
            elif action_type == "impute_knn" and np.issubdtype(processed_df[column].dtype, np.number):
                imputer = KNNImputer(n_neighbors=5); processed_df[[column]] = imputer.fit_transform(processed_df[[column]])
            elif action_type == "impute_iterative" and np.issubdtype(processed_df[column].dtype, np.number):
                imputer = IterativeImputer(max_iter=10, random_state=0); processed_df[[column]] = imputer.fit_transform(processed_df[[column]])
            elif action_type == "to_lowercase" and processed_df[column].dtype == 'object': processed_df[column] = processed_df[column].astype(str).str.lower()
            elif action_type == "to_uppercase" and processed_df[column].dtype == 'object': processed_df[column] = processed_df[column].astype(str).str.upper()
            elif action_type == "trim_whitespace" and processed_df[column].dtype == 'object': processed_df[column] = processed_df[column].astype(str).str.strip()
            elif action_type == "remove_special_characters" and processed_df[column].dtype == 'object': processed_df[column] = processed_df[column].astype(str).str.replace(r'[^a-zA-Z0-9\s]', '', regex=True)
            elif action_type == "one_hot_encode":
                if column.lower() == 'summary': continue
                if processed_df[column].dtype == 'object' or pd.api.types.is_categorical_dtype(processed_df[column]):
                    if processed_df[column].nunique() <= 50: processed_df = pd.get_dummies(processed_df, columns=[column], prefix=column, drop_first=False)
            elif action_type == "label_encode":
                encoder = LabelEncoder(); processed_df[column] = encoder.fit_transform(processed_df[column].astype(str))
            elif action_type == "convert_to_numeric": processed_df[column] = pd.to_numeric(processed_df[column], errors='coerce')
            elif action_type == "convert_to_datetime": processed_df[column] = pd.to_datetime(processed_df[column], errors='coerce')
            elif action_type == "scale_standard" and np.issubdtype(processed_df[column].dtype, np.number):
                scaler = StandardScaler(); processed_df[[column]] = scaler.fit_transform(processed_df[[column]])
            elif action_type == "scale_minmax" and np.issubdtype(processed_df[column].dtype, np.number):
                scaler = MinMaxScaler(); processed_df[[column]] = scaler.fit_transform(processed_df[[column]])
            elif action_type == "transform_log" and np.issubdtype(processed_df[column].dtype, np.number):
                processed_df[column] = processed_df[column].apply(lambda x: np.log1p(x) if x >= 0 else x)
            elif action_type == "handle_outliers_iqr" and np.issubdtype(processed_df[column].dtype, np.number):
                Q1, Q3 = processed_df[column].quantile(0.25), processed_df[column].quantile(0.75); IQR = Q3 - Q1
                lower_bound, upper_bound = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
                processed_df[column] = np.clip(processed_df[column], lower_bound, upper_bound)
            elif 'datetime' in str(processed_df[column].dtype):
                if action_type == "extract_year": processed_df[f'{column}_year'] = processed_df[column].dt.year
                elif action_type == "extract_month": processed_df[f'{column}_month'] = processed_df[column].dt.month
                elif action_type == "extract_day": processed_df[f'{column}_day'] = processed_df[column].dt.day
                elif action_type == "extract_day_of_week": processed_df[f'{column}_day_of_week'] = processed_df[column].dt.dayofweek

        output = BytesIO()
        processed_df.to_csv(output, index=False)
        output.seek(0)
        DatabaseOperations.update_processing_job_status(db, job_id, "completed", output_filename=f"cleaned_{request.file_id}.csv")
        return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=cleaned_file_{request.file_id}.csv"})
    except Exception as e:
        if job_id:
            DatabaseOperations.update_processing_job_status(db, job_id, "failed", error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Data processing failed: {str(e)}")

@app.post("/images/analyze", response_model=ImageAnalysisSummary)
async def analyze_image_dataset(file: UploadFile = File(...), current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip files are supported.")
    contents = await file.read()
    formats, dimensions, modes, image_count = {}, {}, {}, 0
    try:
        with zipfile.ZipFile(BytesIO(contents), 'r') as zip_ref:
            for filename in zip_ref.namelist():
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')) and not filename.startswith('__MACOSX'):
                    image_count += 1
                    with zip_ref.open(filename) as image_file:
                        with Image.open(image_file) as img:
                            formats[img.format] = formats.get(img.format, 0) + 1
                            dimensions[f"{img.width}x{img.height}"] = dimensions.get(f"{img.width}x{img.height}", 0) + 1
                            modes[img.mode] = modes.get(img.mode, 0) + 1
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze zip file: {e}")
    if image_count == 0:
        raise HTTPException(status_code=400, detail="No valid images found in the zip archive.")
    storage_path = os.path.join(UPLOAD_DIR_IMAGES, f"{uuid4().hex}_{file.filename}")
    with open(storage_path, "wb") as f:
        f.write(contents)
    job = DatabaseOperations.create_image_dataset_job(db=db, user_id=current_user.id, filename=file.filename, storage_path=storage_path, image_count=image_count)
    return ImageAnalysisSummary(job_id=job.id, filename=file.filename, image_count=image_count, formats=formats, dimensions=dimensions, modes=modes)

def process_image_dataset_task(job_id: int, actions: List[Dict], db_session: Session):
    try:
        job = db_session.query(ImageDatasetJob).filter(ImageDatasetJob.id == job_id).first()
        if not job: return
        job.processing_status = "processing"
        db_session.commit()
        output_zip_path = job.storage_path.replace(".zip", "_processed.zip")
        with zipfile.ZipFile(job.storage_path, 'r') as original_zip, zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as processed_zip:
            for filename in original_zip.namelist():
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')) and not filename.startswith('__MACOSX'):
                    with original_zip.open(filename) as image_file:
                        img = Image.open(image_file).convert("RGBA")
                        for item in actions:
                            action_type, params = item.get("action"), item.get("params", {})
                            # AFTER THE FIX

                            if action_type == "resize":
                                # Provide default values (e.g., 256) if width or height are missing.
                                width = params.get("width", 256)
                                height = params.get("height", 256)
                                
                                # Ensure the values are valid integers before resizing.
                                if width is None or height is None:
                                    logger.warning(f"Skipping resize for job {job_id} due to missing width/height parameters.")
                                    continue
                                img = img.resize((int(width), int(height)), Image.Resampling.LANCZOS)

                            elif action_type == "grayscale": 
                                img = img.convert("L")
                            elif action_type == "blur": img = img.filter(ImageFilter.GaussianBlur(radius=params.get("radius", 2)))
                            elif action_type == "sharpen": img = img.filter(ImageFilter.SHARPEN)
                            elif action_type == "brightness": img = ImageEnhance.Brightness(img).enhance(params.get("factor", 1.0))
                            elif action_type == "contrast": img = ImageEnhance.Contrast(img).enhance(params.get("factor", 1.0))
                        buffer = BytesIO()
                        if img.mode in ['RGBA', 'P']: img = img.convert('RGB')
                        img.save(buffer, format="JPEG" if img.mode == 'RGB' else "PNG")
                        buffer.seek(0)
                        processed_zip.writestr(filename, buffer.getvalue())
        job.processing_status = "completed"
        job.completed_at = datetime.utcnow()
        job.output_zip_path = output_zip_path
        db_session.commit()
    except Exception as e:
        logger.error(f"Background processing for job {job_id} failed: {e}")
        job.processing_status = "failed"; job.error_message = str(e)
        db_session.commit()
    finally:
        db_session.close()

@app.post("/images/process", status_code=status.HTTP_202_ACCEPTED)
async def process_image_dataset(request: ImageProcessRequest, background_tasks: BackgroundTasks, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ImageDatasetJob).filter(ImageDatasetJob.id == request.job_id, ImageDatasetJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    job.actions_applied = [a.dict() for a in request.actions]
    db.commit()
    background_tasks.add_task(process_image_dataset_task, request.job_id, [a.dict() for a in request.actions], next(get_db()))
    return {"message": "Image dataset processing has started.", "job_id": request.job_id}

@app.get("/images/jobs/{job_id}/status")
async def get_job_status(job_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ImageDatasetJob).filter(ImageDatasetJob.id == job_id, ImageDatasetJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"status": job.processing_status, "error": job.error_message}

@app.get("/images/jobs/{job_id}/download")
async def download_processed_dataset(job_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ImageDatasetJob).filter(ImageDatasetJob.id == job_id, ImageDatasetJob.user_id == current_user.id).first()
    if not job or job.processing_status != "completed" or not job.output_zip_path:
        raise HTTPException(status_code=404, detail="Download not ready or job not found.")
    return FileResponse(path=job.output_zip_path, filename=f"processed_{job.original_zip_filename}", media_type='application/zip')

# --- General Endpoints ---
@app.get("/history")
async def get_upload_history(limit: int = 50, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    uploads = DatabaseOperations.get_user_upload_history(db, current_user.id, limit)
    return {"uploads": [{"id": u.id, "filename": u.original_filename, "file_size": u.file_size, "row_count": u.row_count, "column_count": u.column_count, "upload_timestamp": u.upload_timestamp.isoformat() if u.upload_timestamp else None, "status": u.status} for u in uploads]}

@app.get("/analytics")
async def get_analytics(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        stats = DatabaseOperations.get_usage_statistics(db=db, user_id=current_user.id)
        return stats
    except Exception as e:
        logger.error(f"Error fetching analytics for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch analytics data.")

@app.get("/health")
def health_check():
    db_healthy = check_database_connection()
    return {"status": "healthy" if db_healthy else "degraded", "database": "connected" if db_healthy else "disconnected", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)