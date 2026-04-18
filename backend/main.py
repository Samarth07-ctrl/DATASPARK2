# ==============================================================================
# File: backend/main.py
# ==============================================================================

# --- Python Standard Libraries ---
import os
import json
import asyncio  # Import asyncio for concurrent API calls
import httpx      # Import httpx for async API calls
import numpy as np
import pandas as pd
from io import StringIO, BytesIO
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import zipfile
from uuid import uuid4
from functools import lru_cache # We removed this from the async function, but it's good to know

# --- FastAPI & Related ---
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks, Request, status, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, ConfigDict # <-- IMPORTED ConfigDict
from starlette.responses import StreamingResponse

# --- Database & SQLAlchemy ---
from sqlalchemy.orm import Session, sessionmaker # <-- IMPORTED sessionmaker
from database.config import get_db, check_database_connection, SessionLocal # <-- IMPORTED SessionLocal
from database.operations import DatabaseOperations
from database.auth_operations import AuthOperations
# --- FIX: Added DataProcessingJob import ---
from database.models import User as UserModel, ImageDatasetJob, FileUpload, DataProcessingJob

# --- Scikit-learn & ML ---
# --- FIX: Re-ordered imports ---
# 1. Enable the experimental imputer FIRST
from sklearn.experimental import enable_iterative_imputer
# 2. NOW import all imputers, including the enabled one
from sklearn.impute import KNNImputer, IterativeImputer 
# 3. Import other sklearn tools
from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder
# --- END FIX ---

# --- Image Processing ---
from PIL import Image, ImageFilter, ImageEnhance

# --- Environment Loading ---
from dotenv import load_dotenv
# Load .env file from the same directory as main.py (the 'backend' directory)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Constants for Gemini API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") # Get key from environment variable
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
# --- End Gemini Constants ---

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DataSpark AI Preprocessing API (v9 - Fixed)",
    description="Intelligent API using Gemini with advanced statistical prompting and 'Before vs After' dashboard.",
    version="9.0.0",
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting FastAPI application startup event...")
    
    # Check if API key is loaded
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY environment variable not set. AI analysis will be skipped.")
    else:
        logger.info("Gemini API Key found. AI analysis is enabled.")

    # Check SQL DB connection
    if not check_database_connection():
        logger.critical("Database connection failed! Please run `python backend/create_db.py`")
        # In a real app, you might raise an error to stop startup
        # raise RuntimeError("Database connection failed!")
    else:
        logger.info("Database connection successful.")
    
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

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    created_at: datetime

    # This line is CRITICAL for Pydantic v2 to work with SQLAlchemy models
    model_config = ConfigDict(from_attributes=True) 

class LoginResponse(BaseModel):
    user: UserResponse
    session_token: str
    refresh_token: str
    expires_at: datetime

class ColumnAnalysis(BaseModel):
    column_name: str
    data_type: str
    missing_values: int
    missing_percentage: float
    unique_values: int
    suggestions: List[str] = []
    recommended_action: Optional[str] = None
    is_problematic: bool = False
    ai_insights: Optional[str] = None
    ai_recommendation: Optional[str] = None

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

# Models for the new "Before vs After" Dashboard
class ColumnStats(BaseModel):
    name: str
    missing: int
    outliers: int
    mean: Optional[float] = None
    median: Optional[float] = None

class DashboardAnalysisResponse(BaseModel):
    job_id: int
    analysis: Dict[str, List[ColumnStats]]

# --- File Directories ---
UPLOAD_DIR_CSV = "uploaded_csv_files"
UPLOAD_DIR_IMAGES = "uploaded_image_datasets"
os.makedirs(UPLOAD_DIR_CSV, exist_ok=True)
os.makedirs(UPLOAD_DIR_IMAGES, exist_ok=True)

# --- Authentication Dependency ---
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

# --- Gemini API Call Function (FIXED: No @lru_cache) ---
async def call_gemini_for_analysis(column_name: str, stats: dict, data_sample: list) -> dict:
    """Calls Gemini API to analyze column data and get structured suggestions."""
    if not GEMINI_API_KEY:
        logger.warning(f"Skipping AI analysis for {column_name}: GEMINI_API_KEY not set.")
        return {
            "ai_insight": "AI analysis skipped. API key not configured.",
            "ai_recommendation": "no_action"
        }

    system_prompt = """
    You are a world-class Data Scientist acting as a preprocessing co-pilot.
    Your task is to analyze a column's statistical summary and a sample of its data.
    Provide a concise, actionable insight and a single, primary recommendation for data cleaning.

    Your recommendation MUST be one of the following action keys:
    - 'drop_column': (Use if column has 0 variance, is >95% empty, or is clearly irrelevant)
    - 'convert_to_numeric': (Use if data type is 'object' but sample looks like numbers, e.g., "1,234.56", "$500")
    - 'convert_to_datetime': (Use if data type is 'object' but sample looks like dates/times)
    - 'one_hot_encode': (Use for low-cardinality nominal categorical data, < 50 unique values)
    - 'label_encode': (Use for ordinal data or high-cardinality categorical data, > 50 unique values)
    - 'impute_median': (Use for missing numerical data if skewed, std_dev is high, or outliers are present)
    - 'impute_mean': (Use for missing numerical data if not skewed and normally distributed)
    - 'impute_mode': (Use for missing categorical data)
    - 'no_action': (Use if the column is clean and ready for modeling)
    """
    
    user_query = f"""
    Analyze the column named: '{column_name}'

    STATISTICAL PROFILE:
    {json.dumps(stats, indent=2)}

    DATA SAMPLE (Top 10 most frequent non-null values):
    {data_sample}
    """
    
    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "ai_insight": {"type": "STRING", "description": "Concise insight about the column's quality."},
                    "ai_recommendation": {"type": "STRING", "description": "The single best action key."}
                },
                "required": ["ai_insight", "ai_recommendation"]
            }
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GEMINI_API_URL, json=payload)
            response.raise_for_status()
            
            result = response.json()
            # Handle cases where the API might not return the expected structure
            if 'candidates' not in result or not result['candidates']:
                 raise Exception("Gemini API returned no candidates.")
            if 'parts' not in result['candidates'][0]['content'] or not result['candidates'][0]['content']['parts']:
                 raise Exception("Gemini API returned no content parts.")

            model_output_str = result['candidates'][0]['content']['parts'][0]['text']
            return json.loads(model_output_str)

    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini API HTTP Error for {column_name}: {e.response.text}")
        return {"ai_insight": f"AI analysis failed: HTTP {e.response.status_code}", "ai_recommendation": "no_action"}
    except Exception as e:
        logger.error(f"Error calling Gemini for {column_name}: {e}")
        return {"ai_insight": f"AI analysis failed: {str(e)}", "ai_recommendation": "no_action"}

# --- Core Column Analysis Function (FIXED: JSON Serializable) ---
def get_column_stats(df: pd.DataFrame, column_name: str) -> ColumnStats:
    """Helper function to extract clean stats from a column."""
    col = df[column_name]
    missing = int(col.isnull().sum())
    outliers = 0
    mean = None
    median = None
    
    if np.issubdtype(col.dtype, np.number):
        try:
            # FIX: Check for NaNs before quantile calculation
            if not col.dropna().empty:
                Q1 = col.quantile(0.25)
                Q3 = col.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                outliers = int(((col < lower_bound) | (col > upper_bound)).sum())
            mean = float(col.mean()) # mean() handles NaNs
            median = float(col.median()) # median() handles NaNs
        except Exception as e:
            logger.warning(f"Could not calculate stats for numeric column {column_name}: {e}")
            pass # Keep defaults
            
    return ColumnStats(
        name=column_name,
        missing=missing,
        outliers=outliers,
        mean=mean if pd.notna(mean) else None, # Ensure NaN/NaT are converted to None
        median=median if pd.notna(median) else None
    )

async def analyze_column_with_ai(df: pd.DataFrame, column_name: str) -> ColumnAnalysis:
    """Analyzes a single column, generates statistical suggestions, and queries Gemini for deep insights."""
    try:
        col = df[column_name]
        data_type = str(col.dtype)
        missing_values = int(col.isnull().sum())
        total_rows = len(df)
        missing_percentage = round((missing_values / total_rows) * 100, 2) if total_rows > 0 else 0
        unique_values_count = int(col.nunique())
        
        suggestions = ["no_action", "drop_column"]
        recommended_action = "no_action"
        is_problematic = False
        
        # --- FIX: Create a dictionary with standard Python types ---
        stats_summary = {
            'data_type': data_type,
            'missing_percentage': float(missing_percentage),
            'unique_values_count': int(unique_values_count),
            'total_rows': int(total_rows)
        }
        
        # --- 1. Statistical (Rule-Based) Analysis ---
        if missing_values > 0:
            is_problematic = True
            suggestions.append("drop_missing_rows")
            if np.issubdtype(col.dtype, np.number):
                try:
                    # FIX: Cast skewness to float
                    skew_val = col.skew()
                    stats_summary['skewness'] = float(skew_val) if pd.notna(skew_val) else None
                    if stats_summary['skewness'] is not None:
                        recommended_action = "impute_median" if abs(stats_summary['skewness']) > 1 else "impute_mean"
                except Exception:
                    recommended_action = "impute_mean"
                suggestions.extend(["impute_mean", "impute_median", "impute_knn", "impute_iterative"])
            else: # Object or other type
                recommended_action = "impute_mode"
                suggestions.append("impute_mode")

        if data_type == 'object':
            suggestions.extend(["to_lowercase", "to_uppercase", "trim_whitespace", "remove_special_characters", "convert_to_datetime", "convert_to_numeric"])
            if 1 < unique_values_count <= 50:
                suggestions.extend(["one_hot_encode", "label_encode"])
                if not recommended_action: recommended_action = "one_hot_encode"
        
        if np.issubdtype(col.dtype, np.number):
            # FIX: Cast all numpy types to standard python float, handle NaNs
            stats_summary['mean'] = float(col.mean()) if pd.notna(col.mean()) else None
            stats_summary['median'] = float(col.median()) if pd.notna(col.median()) else None
            stats_summary['std_dev'] = float(col.std()) if pd.notna(col.std()) else None
            stats_summary['min'] = float(col.min()) if pd.notna(col.min()) else None
            stats_summary['max'] = float(col.max()) if pd.notna(col.max()) else None
            
            if stats_summary.get('std_dev', -1) == 0:
                is_problematic = True
                recommended_action = "drop_column"
                suggestions.insert(0, "drop_column")
            suggestions.extend(["scale_standard", "scale_minmax", "transform_log", "handle_outliers_iqr"])
        
        if 'datetime' in data_type:
            suggestions.extend(['extract_year', 'extract_month', 'extract_day', 'extract_day_of_week'])
        
        # --- 2. AI-Powered (Gemini) Analysis ---
        if not col.dropna().empty:
            data_sample = col.dropna().value_counts().head(10).index.astype(str).tolist()
        else:
            data_sample = []
            
        gemini_response = await call_gemini_for_analysis(column_name, stats_summary, data_sample)
        
        ai_insights = gemini_response.get('ai_insight')
        ai_recommendation = gemini_response.get('ai_recommendation')
        
        # --- 3. Final Recommendation Logic ---
        if ai_recommendation and ai_recommendation != "no_action":
            is_problematic = True
            if ai_recommendation not in suggestions:
                suggestions.insert(0, ai_recommendation)
            recommended_action = ai_recommendation
            
        return ColumnAnalysis(
            column_name=column_name, 
            data_type=data_type, 
            missing_values=missing_values, 
            missing_percentage=missing_percentage, 
            unique_values=unique_values_count, 
            suggestions=list(dict.fromkeys(suggestions)), # Remove duplicates
            recommended_action=recommended_action, 
            is_problematic=is_problematic,
            ai_insights=ai_insights,
            ai_recommendation=ai_recommendation
        )

    except Exception as e:
        logger.error(f"Critical analysis failure for '{column_name}': {e}", exc_info=True)
        # --- FIX: Safer fallback on critical error ---
        return ColumnAnalysis(
            column_name=column_name, 
            data_type="unknown", 
            missing_values=0, 
            missing_percentage=0, 
            unique_values=0, 
            suggestions=["drop_column"],
            recommended_action="no_action", # Default to no_action, not drop
            is_problematic=True,
            ai_insights=f"Critical analysis failure: {str(e)}",
            ai_recommendation="no_action"
        )

# --- API Endpoints ---

@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    try:
        user = AuthOperations.create_user(db=db, username=user_data.username, email=user_data.email, password=user_data.password, first_name=user_data.first_name, last_name=user_data.last_name)
        return user # Pydantic v2 will auto-convert from the ORM model
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed")

@app.post("/auth/login", response_model=LoginResponse)
async def login_user(login_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    try:
        user = AuthOperations.authenticate_user(db=db, username_or_email=login_data.username_or_email, password=login_data.password)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
        session = AuthOperations.create_session(db=db, user_id=user.id, user_agent=request.headers.get("User-Agent"), ip_address=request.client.host)
        
        return LoginResponse(
            user=user, # Pydantic v2 handles the ORM conversion
            session_token=session.session_token,
            refresh_token=session.refresh_token,
            expires_at=session.expires_at
        )
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
    return current_user # Pydantic v2 handles the conversion

# --- TABULAR (CSV) WORKFLOW ---

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
    
    try:
        df = pd.read_csv(StringIO(content_str))
    except Exception as e:
        logger.error(f"Pandas read_csv error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV file: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV file is empty or could not be parsed")
    
    row_count, col_count = df.shape
    
    # Run all AI analyses concurrently
    analysis_tasks = [analyze_column_with_ai(df, col) for col in df.columns]
    analysis_results = await asyncio.gather(*analysis_tasks)
    
    response_data = {"filename": file.filename, "row_count": row_count, "column_count": col_count, "column_analysis": [ar.dict() for ar in analysis_results]}
    
    # Save the full AI analysis to the DB
    background_tasks.add_task(DatabaseOperations.save_analysis_result, db, db_file_upload.id, response_data, current_user.id)
    
    return AnalysisResponse(**response_data, file_id=db_file_upload.id)

@app.post("/process", response_model=DashboardAnalysisResponse)
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
        
        # --- "BEFORE" ANALYSIS ---
        before_stats = [get_column_stats(df, col) for col in df.columns]
        
        processed_df = df.copy()
        
        # --- APPLYING ACTIONS (The Mapping Logic) ---
        for action_item in request.actions:
            column = action_item.column
            action_type = action_item.action
            if column not in processed_df.columns: continue

            try:
                if action_type == "drop_column":
                    processed_df.drop(columns=[column], inplace=True)
                elif action_type == "drop_missing_rows":
                    processed_df.dropna(subset=[column], inplace=True)
                
                # --- Imputation ---
                elif action_type == "impute_mean" and np.issubdtype(processed_df[column].dtype, np.number):
                    processed_df[column].fillna(processed_df[column].mean(), inplace=True)
                elif action_type == "impute_median" and np.issubdtype(processed_df[column].dtype, np.number):
                    processed_df[column].fillna(processed_df[column].median(), inplace=True)
                elif action_type == "impute_mode":
                    # Ensure mode() doesn't return an empty Series
                    if not processed_df[column].mode().empty:
                        processed_df[column].fillna(processed_df[column].mode()[0], inplace=True)
                elif action_type == "impute_knn" and np.issubdtype(processed_df[column].dtype, np.number):
                    imputer = KNNImputer(n_neighbors=5); processed_df[[column]] = imputer.fit_transform(processed_df[[column]])
                elif action_type == "impute_iterative" and np.issubdtype(processed_df[column].dtype, np.number):
                    imputer = IterativeImputer(max_iter=10, random_state=0); processed_df[[column]] = imputer.fit_transform(processed_df[[column]])
                
                # --- Text/Object Cleaning ---
                elif action_type == "to_lowercase" and processed_df[column].dtype == 'object': processed_df[column] = processed_df[column].astype(str).str.lower()
                elif action_type == "to_uppercase" and processed_df[column].dtype == 'object': processed_df[column] = processed_df[column].astype(str).str.upper()
                elif action_type == "trim_whitespace" and processed_df[column].dtype == 'object': processed_df[column] = processed_df[column].astype(str).str.strip()
                elif action_type == "remove_special_characters" and processed_df[column].dtype == 'object': processed_df[column] = processed_df[column].astype(str).str.replace(r'[^a-zA-Z0-9\s.-]', '', regex=True) # Kept . and -
                
                # --- Type Conversion (AI Suggested) ---
                elif action_type == "convert_to_numeric":
                    # Clean common currency/number symbols before converting
                    processed_df[column] = processed_df[column].astype(str).str.replace(r'[$,]', '', regex=True)
                    processed_df[column] = pd.to_numeric(processed_df[column], errors='coerce')
                elif action_type == "convert_to_datetime":
                    processed_df[column] = pd.to_datetime(processed_df[column], errors='coerce')
                
                # --- Encoding ---
                elif action_type == "one_hot_encode":
                    if processed_df[column].dtype == 'object' or pd.api.types.is_categorical_dtype(processed_df[column]):
                        if processed_df[column].nunique() <= 50: processed_df = pd.get_dummies(processed_df, columns=[column], prefix=column, drop_first=False)
                elif action_type == "label_encode":
                    encoder = LabelEncoder(); processed_df[column] = encoder.fit_transform(processed_df[column].astype(str))
                
                # --- Scaling & Transformation ---
                elif action_type == "scale_standard" and np.issubdtype(processed_df[column].dtype, np.number):
                    scaler = StandardScaler(); processed_df[[column]] = scaler.fit_transform(processed_df[[column]])
                elif action_type == "scale_minmax" and np.issubdtype(processed_df[column].dtype, np.number):
                    scaler = MinMaxScaler(); processed_df[[column]] = scaler.fit_transform(processed_df[[column]])
                elif action_type == "transform_log" and np.issubdtype(processed_df[column].dtype, np.number):
                    processed_df[column] = processed_df[column].apply(lambda x: np.log1p(x) if x >= 0 else x)
                
                # --- Outlier Handling ---
                elif action_type == "handle_outliers_iqr" and np.issubdtype(processed_df[column].dtype, np.number):
                    Q1, Q3 = processed_df[column].quantile(0.25), processed_df[column].quantile(0.75); IQR = Q3 - Q1
                    lower_bound, upper_bound = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
                    processed_df[column] = np.clip(processed_df[column], lower_bound, upper_bound)
                
                # --- Datetime Feature Extraction ---
                elif 'datetime' in str(processed_df[column].dtype):
                    if action_type == "extract_year": processed_df[f'{column}_year'] = processed_df[column].dt.year
                    elif action_type == "extract_month": processed_df[f'{column}_month'] = processed_df[column].dt.month
                    elif action_type == "extract_day": processed_df[f'{column}_day'] = processed_df[column].dt.day
                    elif action_type == "extract_day_of_week": processed_df[f'{column}_day_of_week'] = processed_df[column].dt.dayofweek
            
            except Exception as col_e:
                logger.error(f"Failed to apply action '{action_type}' on column '{column}': {col_e}")
                # Optionally skip this action and continue
                pass

        # --- "AFTER" ANALYSIS ---
        after_stats = [get_column_stats(processed_df, col) for col in processed_df.columns]
        
        # Save the processed file to a new path for download
        output_filename = f"cleaned_{job_id}_{file_record.original_filename}"
        output_storage_path = os.path.join(UPLOAD_DIR_CSV, output_filename)
        processed_df.to_csv(output_storage_path, index=False)
        
        DatabaseOperations.update_processing_job_status(db, job_id, "completed", output_filename=output_filename)
        
        return DashboardAnalysisResponse(
            job_id=job_id,
            analysis={
                "before": [s.dict() for s in before_stats],
                "after": [s.dict() for s in after_stats]
            }
        )
        
    except Exception as e:
        logger.error(f"Error during data processing: {e}", exc_info=True)
        if job_id:
            DatabaseOperations.update_processing_job_status(db, job_id, "failed", error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Data processing failed: {str(e)}")

@app.get("/download/job/{job_id}", response_class=FileResponse)
async def download_processed_file(job_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Downloads the processed CSV file from a completed job."""
    job = db.query(DataProcessingJob).filter(
        DataProcessingJob.id == job_id, 
        DataProcessingJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.processing_status != "completed":
        raise HTTPException(status_code=400, detail="Job is not yet complete.")
    if not job.output_filename:
        raise HTTPException(status_code=404, detail="Output file not found.")
        
    file_path = os.path.join(UPLOAD_DIR_CSV, job.output_filename)
    if not os.path.exists(file_path):
        logger.error(f"File not found on disk: {file_path}")
        raise HTTPException(status_code=404, detail="Processed file not found on server.")
        
    return FileResponse(
        path=file_path,
        filename=job.output_filename,
        media_type='text/csv'
    )

# --- IMAGE WORKFLOW ---

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

def process_image_dataset_task(job_id: int, actions: List[Dict], db_session_factory: sessionmaker):
    """Background task for processing images."""
    db_session = db_session_factory()
    job = None # Define job outside the try block
    try:
        # Get the job first
        job = db_session.query(ImageDatasetJob).filter(ImageDatasetJob.id == job_id).first()
        if not job: 
            logger.error(f"Image job {job_id} not found in DB for background task.")
            return
            
        job.processing_status = "processing"
        db_session.commit()
        
        # --- Start Main Processing ---
        output_zip_path = job.storage_path.replace(".zip", "_processed.zip")
        
        with zipfile.ZipFile(job.storage_path, 'r') as original_zip, \
             zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as processed_zip:
            
            for filename in original_zip.namelist():
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')) and not filename.startswith('__MACOSX'):
                    with original_zip.open(filename) as image_file:
                        img = Image.open(image_file).convert("RGBA") # Convert to RGBA for consistency
                        
                        for item in actions:
                            action_type = item.get("action")
                            params = item.get("params", {})
                            
                            if action_type == "resize":
                                width = int(params.get("width", 256))
                                height = int(params.get("height", 256))
                                img = img.resize((width, height), Image.Resampling.LANCZOS)
                            elif action_type == "grayscale": 
                                img = img.convert("L")
                            elif action_type == "blur": 
                                img = img.filter(ImageFilter.GaussianBlur(radius=float(params.get("radius", 2))))
                            elif action_type == "sharpen": 
                                img = img.filter(ImageFilter.SHARPEN)
                            elif action_type == "brightness": 
                                img = ImageEnhance.Brightness(img).enhance(float(params.get("factor", 1.0)))
                            elif action_type == "contrast": 
                                img = ImageEnhance.Contrast(img).enhance(float(params.get("factor", 1.0)))
                        
                        buffer = BytesIO()
                        # Handle grayscale conversion for saving
                        save_format = "PNG" # Default to PNG for quality and transparency
                        if img.mode == 'L':
                            save_format = "PNG" # Save grayscale as PNG
                        elif img.mode in ['RGBA', 'P'] and not any(action['action'] == 'grayscale' for action in actions):
                             save_format = "PNG" # Preserve transparency if not grayscaled
                        else:
                            # If it's RGB (or converted to L), JPEG is fine
                            img = img.convert('RGB')
                            save_format = "JPEG"
                            
                        img.save(buffer, format=save_format)
                        buffer.seek(0)
                        processed_zip.writestr(filename, buffer.getvalue())
        # --- End Main Processing ---

        job.processing_status = "completed"
        job.completed_at = datetime.utcnow()
        job.output_zip_path = output_zip_path
        db_session.commit()
        
    except Exception as e:
        logger.error(f"Background processing for job {job_id} failed: {e}", exc_info=True)
        # --- FIX IS HERE ---
        # Now 'job' will be defined (or None)
        if job:
            job.processing_status = "failed"; job.error_message = str(e)
            db_session.commit()
        # If job is None (failed to even query it), we can't update it.
        # But we must ensure the session is closed.
    finally:
        db_session.close()

@app.post("/images/process", status_code=status.HTTP_202_ACCEPTED)
async def process_image_dataset(request: ImageProcessRequest, background_tasks: BackgroundTasks, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ImageDatasetJob).filter(ImageDatasetJob.id == request.job_id, ImageDatasetJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    job.actions_applied = [a.dict() for a in request.actions]
    db.commit()
    
    # Pass the SessionLocal factory, not a live session
    background_tasks.add_task(process_image_dataset_task, request.job_id, [a.dict() for a in request.actions], SessionLocal)
    
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
    
    if not os.path.exists(job.output_zip_path):
        logger.error(f"Processed image zip not found on disk: {job.output_zip_path}")
        raise HTTPException(status_code=404, detail="Processed file not found on server.")
        
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
    # redis_healthy = check_redis_connection() # Assuming redis is not yet integrated
    redis_healthy = True # Placeholder
    return {
        "status": "healthy" if (db_healthy and redis_healthy) else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "redis_status": "connected" if redis_healthy else "disconnected",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    # This block is for running directly (e.g., python main.py)
    # uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    # Note: The 'app' object must be available, so we just run uvicorn as a command
    pass