# ==============================================================================
# File: backend/main.py
# ==============================================================================

# --- Python Standard Libraries ---
import os
import json
import asyncio
import httpx
import numpy as np
import pandas as pd
import polars as pl           # Phase 2: High-perf DataFrame engine
from io import StringIO, BytesIO
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import zipfile
from uuid import uuid4
import secrets

# --- FastAPI & Related ---
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks, Request, status, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, ConfigDict
from starlette.responses import StreamingResponse

# --- Database & SQLAlchemy ---
from sqlalchemy.orm import Session, sessionmaker
from database.config import get_db, check_database_connection, SessionLocal
from database.operations import DatabaseOperations
from database.auth_operations import AuthOperations
from database.models import User as UserModel, ImageDatasetJob, FileUpload, DataProcessingJob, AnalysisResult

# --- Scikit-learn & ML ---
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import KNNImputer, IterativeImputer
from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder

# --- Image Processing ---
from PIL import Image, ImageFilter, ImageEnhance

# --- Phase 3: Enterprise Security ---
import jwt  # PyJWT for JWT token encoding/decoding
from services.pii_masking import mask_column_profiles, get_pii_status

# --- Environment Loading ---
from dotenv import load_dotenv
# Load .env file from the same directory as main.py (the 'backend' directory)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Constants for Gemini API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

# --- Phase 3: JWT Configuration ---
# WHY JWT over session tokens?
# Session tokens require a DB lookup on EVERY request. JWTs are self-contained:
# the server can verify them with just the secret key (no DB query needed).
# This reduces latency and enables horizontal scaling across multiple servers.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(64))
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7

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

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY environment variable not set. AI analysis will be skipped.")
    else:
        logger.info("Gemini API Key found. AI analysis is enabled.")

    # PII masking status
    pii_status = get_pii_status()
    if pii_status['enabled']:
        logger.info(f"PII Masking ENABLED via {pii_status['engine']}. Scanning for: {', '.join(pii_status['entities_scanned'][:5])}...")
    else:
        logger.warning("PII Masking DISABLED. Data samples will be sent unmasked to Gemini API.")

    # JWT mode
    logger.info(f"JWT auth configured. Algorithm: {JWT_ALGORITHM}, Access token TTL: {JWT_ACCESS_TOKEN_EXPIRE_MINUTES}min")

    if not check_database_connection():
        logger.critical("Database connection failed! Please run `python backend/create_db.py`")
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
    expose_headers=["Content-Disposition"]
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
    role: Optional[str] = "user"  # Phase 3: RBAC role field

    model_config = ConfigDict(from_attributes=True)

class LoginResponse(BaseModel):
    user: UserResponse
    session_token: str
    refresh_token: str
    expires_at: datetime

class JWTLoginResponse(BaseModel):
    """Response for the new JWT-based login endpoint."""
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

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
    target_column: Optional[str] = None    # Feature 3: column selected as ML target
    apply_smote: bool = False               # Feature 3: whether to apply SMOTE balancing

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

# --- Feature 2: Advanced Visualization Data Models ---
class HistogramBin(BaseModel):
    """A single histogram bin with its range and count."""
    bin_start: float
    bin_end: float
    count: int

class ColumnHistogram(BaseModel):
    """Histogram data for a single numeric column."""
    column_name: str
    bins: List[HistogramBin]

class MissingMatrix(BaseModel):
    """Lightweight binary matrix showing null positions (sampled rows)."""
    columns: List[str]
    data: List[List[int]]  # Each inner list is a row: 0=present, 1=missing
    total_rows: int
    sampled_rows: int

class CorrelationMatrix(BaseModel):
    """Pearson correlation matrix for numeric features."""
    columns: List[str]
    matrix: List[List[Optional[float]]]

class VisualizationData(BaseModel):
    """All visualization payloads for the Before vs After dashboard."""
    missing_matrix_before: Optional[MissingMatrix] = None
    missing_matrix_after: Optional[MissingMatrix] = None
    histograms_before: Optional[List[ColumnHistogram]] = None
    histograms_after: Optional[List[ColumnHistogram]] = None
    correlation_before: Optional[CorrelationMatrix] = None
    correlation_after: Optional[CorrelationMatrix] = None

class DashboardAnalysisResponse(BaseModel):
    job_id: int
    analysis: Dict[str, List[ColumnStats]]
    visualization_data: Optional[VisualizationData] = None
    filename: Optional[str] = None  # Feature 4: included for historical job lookups

# --- File Directories ---
UPLOAD_DIR_CSV = "uploaded_csv_files"
UPLOAD_DIR_IMAGES = "uploaded_image_datasets"
os.makedirs(UPLOAD_DIR_CSV, exist_ok=True)
os.makedirs(UPLOAD_DIR_IMAGES, exist_ok=True)

# --- Authentication Dependency (HYBRID: JWT + Session Token) ---
# WHY HYBRID?
# The frontend currently uses session tokens. Switching to JWT requires
# a frontend update. This hybrid approach accepts BOTH: it tries to decode
# the Bearer token as a JWT first, and if that fails, falls back to the
# legacy session-token DB lookup. This enables a gradual migration.

from services.jwt_auth import decode_token as jwt_decode, create_access_token, create_refresh_token
from services.oauth_sso import get_authorization_url, exchange_code_for_user_info, get_sso_status, get_available_providers

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security),
                           db: Session = Depends(get_db)) -> UserModel:
    token = credentials.credentials

    # Attempt 1: Try JWT decode (no DB hit needed)
    jwt_payload = jwt_decode(token)
    if jwt_payload and jwt_payload.get("type") == "access":
        try:
            user_id = int(jwt_payload["sub"])
            user = db.query(UserModel).filter(UserModel.id == user_id).first()
            if user and user.is_active:
                return user
        except (ValueError, KeyError):
            pass

    # Attempt 2: Fall back to legacy session token (DB lookup)
    user = AuthOperations.get_user_by_session_token(db, token)
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

# ==============================================================================
# GEMINI AI ANALYSIS — BATCHED SINGLE-PROMPT ARCHITECTURE
# ==============================================================================
#
# WHY BATCHING?
# The old code made one Gemini API call per column (N calls for N columns).
# A 50-column dataset = 50 API calls = frequent 429 rate-limit errors.
# The new architecture sends ALL column stats in ONE prompt and gets back
# a JSON array of results. This is:
#   1. Faster — 1 round-trip instead of N
#   2. Cheaper — 1 API call instead of N
#   3. Rate-limit safe — impossible to hit per-minute quotas on a single call
#   4. Context-aware — the AI can see cross-column relationships
# ==============================================================================

# ==============================================================================
# CONTEXT-AWARE SYSTEM PROMPT FACTORY
# ==============================================================================
# WHY DYNAMIC PROMPTS?
# A static prompt treats all datasets the same. But a user training XGBoost
# does NOT need StandardScaler, and a user building a BI dashboard does NOT
# need label encoding.  By injecting the user's objective + model type into
# the system prompt, Gemini's recommendations become surgically precise.
# ==============================================================================

_BASE_SYSTEM_PROMPT = """
You are a world-class Data Scientist acting as a preprocessing co-pilot.
You will receive a JSON array of column profiles for an entire dataset.
For EACH column, provide a concise, actionable insight and a single primary recommendation.

Your recommendation for each column MUST be one of these action keys:
- 'drop_column': (column has 0 variance, is >95% empty, or is clearly irrelevant like an ID)
- 'convert_to_numeric': (data type is 'object' but sample looks like numbers, e.g., "1,234.56", "$500")
- 'convert_to_datetime': (data type is 'object' but sample looks like dates/times)
- 'one_hot_encode': (low-cardinality nominal categorical data, < 50 unique values)
- 'label_encode': (ordinal or high-cardinality categorical data, > 50 unique values)
- 'impute_median': (missing numerical data that is skewed, has high std_dev, or outliers)
- 'impute_mean': (missing numerical data that is not skewed and normally distributed)
- 'impute_mode': (missing categorical data)
- 'scale_standard': (standardize numeric features to zero mean, unit variance)
- 'scale_minmax': (normalize numeric features to [0, 1] range)
- 'no_action': (the column is clean and ready for use)

Return a JSON array where each element has:
  - "column_name": the exact column name from the input
  - "ai_insight": a concise insight about the column's quality
  - "ai_recommendation": the single best action key from the list above
"""

# Objective-specific prompt fragments injected after the base prompt
_CONTEXT_PROMPTS = {
    "eda": """
--- USER OBJECTIVE: Exploratory Data Analysis (EDA) ---
The user wants to EXPLORE and UNDERSTAND their data, NOT build a model.
Prioritize data quality and interpretability:
- Focus on revealing data issues: missing patterns, outliers, skewness.
- DO NOT recommend encoding (one-hot or label) unless the column is fundamentally broken.
- DO NOT recommend scaling — raw distributions are more informative for EDA.
- Prefer imputation that preserves distribution shape (median for skewed, mean for normal).
- Flag columns with suspicious patterns (e.g., constant values, near-zero variance).
- Recommend 'convert_to_datetime' aggressively for date-like strings.
""",
    "machine_learning": {
        "tree_based": """
--- USER OBJECTIVE: Machine Learning — Tree-Based Models (XGBoost, Random Forest, LightGBM) ---
Tree-based models are scale-invariant and handle non-linear relationships natively.
Critical constraints:
- NEVER recommend 'scale_standard' or 'scale_minmax' — trees split on thresholds, scaling is WASTED computation.
- Prefer 'label_encode' over 'one_hot_encode' for categorical features — XGBoost handles ordinal integers efficiently and one-hot creates sparse, high-dimensional data.
- Missing values: XGBoost/LightGBM handle NaN natively. Only recommend imputation if missing% > 50%.
- Don't worry about skewness or non-normality — trees are not affected.
- Flag high-cardinality categoricals (>100 unique) as potential target-encoding candidates.
""",
        "linear_models": """
--- USER OBJECTIVE: Machine Learning — Linear Models (Linear/Logistic Regression, SVM, KNN) ---
Linear models assume linearity, feature independence, and are highly sensitive to scale.
Critical constraints:
- ALWAYS recommend 'scale_standard' for numeric features — unscaled features will dominate the model.
- Prefer 'one_hot_encode' over 'label_encode' for nominal categoricals — label encoding implies false ordinal relationships.
- Flag highly skewed numeric columns — recommend 'transform_log' or 'impute_median'.
- Flag potential multicollinearity (mention correlation if data_sample suggests it).
- Impute missing values aggressively — linear models CANNOT handle NaN.
""",
        "deep_learning": """
--- USER OBJECTIVE: Machine Learning — Deep Learning / Neural Networks ---
Neural nets require normalized, dense numeric inputs.
Critical constraints:
- ALWAYS recommend 'scale_minmax' for numeric features to bring values into [0, 1] range — this helps gradient descent converge faster.
- Prefer 'label_encode' over 'one_hot_encode' (use embeddings for categoricals at the model level). Only suggest one-hot if cardinality < 10.
- Flag high-cardinality categoricals (>50 unique) — suggest label_encode + embedding.
- Impute ALL missing values — neural nets cannot handle NaN at all.
- Flag datetime columns for extraction (year, month, day_of_week) as separate numeric features.
""",
    },
    "bi_reporting": """
--- USER OBJECTIVE: Business Intelligence / Reporting ---
The user wants clean, human-readable data for dashboards (Tableau, Power BI, etc.).
Critical constraints:
- NEVER recommend encoding (one_hot_encode, label_encode) — BI tools need human-readable category names.
- NEVER recommend scaling — raw values are needed for charts and KPIs.
- Preserve original data types where possible. Recommend 'convert_to_numeric' only for obvious number-as-text issues.
- Recommend 'convert_to_datetime' aggressively for date strings — BI tools leverage dates for time-series analysis.
- Recommend 'trim_whitespace' and 'to_lowercase' for text cleanup (consistency in filters/group-by).
- For missing values, prefer 'impute_mode' for categoricals and 'impute_median' for numerics.
- Suggest datetime extraction (extract_year, extract_month) for time-based analysis.
""",
}


def _build_context_aware_prompt(objective: Optional[str] = None, model_type: Optional[str] = None) -> str:
    """Builds the Gemini system prompt by combining the base instructions with context-specific guidance."""
    prompt = _BASE_SYSTEM_PROMPT

    if not objective:
        return prompt

    context = _CONTEXT_PROMPTS.get(objective)
    if context is None:
        return prompt

    # ML objective has nested model-type prompts
    if isinstance(context, dict):
        model_context = context.get(model_type or "", "")
        if model_context:
            prompt += "\n" + model_context
        else:
            # ML selected but no model type — give generic ML guidance
            prompt += "\n--- USER OBJECTIVE: Machine Learning (model type not specified) ---\n"
            prompt += "Prioritize missing value handling and encoding. Recommend scaling where appropriate.\n"
    else:
        prompt += "\n" + context

    logger.info(f"Built context-aware prompt for objective='{objective}', model_type='{model_type}'")
    return prompt


async def call_gemini_batch_analysis(
    columns_profile: List[Dict],
    objective: Optional[str] = None,
    model_type: Optional[str] = None
) -> List[Dict]:
    """
    Sends ALL column profiles to Gemini in a single batched API call.
    Returns a list of {column_name, ai_insight, ai_recommendation} dicts.
    Falls back to empty results (no_action) if the API call fails.
    """
    if not GEMINI_API_KEY:
        logger.warning("Skipping AI analysis: GEMINI_API_KEY not set.")
        return [
            {
                "column_name": col["column_name"],
                "ai_insight": "AI analysis skipped. API key not configured.",
                "ai_recommendation": "no_action"
            }
            for col in columns_profile
        ]

    # Build the context-aware system prompt
    system_prompt = _build_context_aware_prompt(objective, model_type)

    user_query = f"""
Analyze the following dataset with {len(columns_profile)} columns.
For each column, provide your insight and recommendation.

DATASET COLUMN PROFILES:
{json.dumps(columns_profile, indent=2)}
"""

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "column_name": {"type": "STRING"},
                        "ai_insight": {"type": "STRING", "description": "Concise insight about the column's quality."},
                        "ai_recommendation": {"type": "STRING", "description": "The single best action key."}
                    },
                    "required": ["column_name", "ai_insight", "ai_recommendation"]
                }
            }
        },
    }

    try:
        # Use a longer timeout for batch analysis (all columns at once)
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(GEMINI_API_URL, json=payload)
            response.raise_for_status()

            result = response.json()
            if 'candidates' not in result or not result['candidates']:
                raise Exception("Gemini API returned no candidates.")
            if 'parts' not in result['candidates'][0]['content'] or not result['candidates'][0]['content']['parts']:
                raise Exception("Gemini API returned no content parts.")

            model_output_str = result['candidates'][0]['content']['parts'][0]['text']
            parsed = json.loads(model_output_str)

            # Validate it's a list
            if not isinstance(parsed, list):
                raise Exception(f"Expected array response, got {type(parsed).__name__}")

            logger.info(f"Gemini batch analysis returned {len(parsed)} column results.")
            return parsed

    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini batch API HTTP Error: {e.response.status_code} — {e.response.text[:500]}")
    except Exception as e:
        logger.error(f"Gemini batch analysis failed: {e}")

    # Fallback: return no_action for all columns
    return [
        {
            "column_name": col["column_name"],
            "ai_insight": "AI analysis failed. Using rule-based recommendations.",
            "ai_recommendation": "no_action"
        }
        for col in columns_profile
    ]


# ==============================================================================
# POLARS-BASED COLUMN PROFILING & STATS
# ==============================================================================
# WHY POLARS?
# Polars is a Rust-backed DataFrame library that is 5-10x faster than Pandas
# for most analytical operations. It uses multi-threading by default and has
# zero-copy memory layout.  We use it for the read-heavy profiling path
# (/analyze) where we compute stats on every column. The write-heavy processing
# path (/process) stays on Pandas because scikit-learn requires numpy arrays.
# ==============================================================================

def _safe_scalar(val) -> Optional[float]:
    """Safely extract a scalar from a Polars expression result. Returns None for null/NaN."""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return f
    except (TypeError, ValueError):
        return None


def get_column_stats_polars(df_pl: pl.DataFrame, column_name: str) -> ColumnStats:
    """Polars-based column stats for before/after dashboard."""
    col = df_pl[column_name]
    missing = col.null_count()
    outliers = 0
    mean = None
    median = None

    if col.dtype in (pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                     pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
        try:
            non_null = col.drop_nulls()
            if len(non_null) > 0:
                q1 = non_null.quantile(0.25)
                q3 = non_null.quantile(0.75)
                if q1 is not None and q3 is not None:
                    iqr = q3 - q1
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    outliers = int(((col < lower) | (col > upper)).sum())
            mean = _safe_scalar(col.mean())
            median = _safe_scalar(col.median())
        except Exception as e:
            logger.warning(f"Polars stats error for {column_name}: {e}")

    return ColumnStats(
        name=column_name,
        missing=int(missing),
        outliers=outliers,
        mean=mean,
        median=median
    )


def get_column_stats(df: pd.DataFrame, column_name: str) -> ColumnStats:
    """Pandas-based column stats — used by /process endpoint which operates on Pandas DFs."""
    col = df[column_name]
    missing = int(col.isnull().sum())
    outliers = 0
    mean = None
    median = None

    if np.issubdtype(col.dtype, np.number):
        try:
            if not col.dropna().empty:
                Q1 = col.quantile(0.25)
                Q3 = col.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                outliers = int(((col < lower_bound) | (col > upper_bound)).sum())
            mean = float(col.mean())
            median = float(col.median())
        except Exception as e:
            logger.warning(f"Could not calculate stats for numeric column {column_name}: {e}")

    return ColumnStats(
        name=column_name,
        missing=missing,
        outliers=outliers,
        mean=mean if pd.notna(mean) else None,
        median=median if pd.notna(median) else None
    )


# ==============================================================================
# FEATURE 2: VISUALIZATION DATA COMPUTATION
# ==============================================================================
# These functions compute aggregated, lightweight visualization payloads from
# Pandas DataFrames.  They are used by the /process endpoint to generate
# "Before vs After" charts WITHOUT ever sending raw data to the frontend.
# ==============================================================================

MAX_HEATMAP_ROWS = 50   # Max sampled rows for the missing-value heatmap
HISTOGRAM_BINS = 20     # Number of bins for distribution histograms


def _compute_missing_matrix(df: pd.DataFrame) -> Optional[MissingMatrix]:
    """
    Returns a binary matrix of null positions for a sampled subset of rows.
    Used to render a "missing values heatmap" on the frontend.
    WHY SAMPLE? A 100k-row dataset → 100k × N matrix is too large.
    50 evenly-spaced rows capture the null *pattern* without bloating the payload.
    """
    try:
        total_rows = len(df)
        if total_rows == 0:
            return None

        # Evenly-spaced sampling to capture distribution of nulls
        if total_rows <= MAX_HEATMAP_ROWS:
            sample_df = df
        else:
            indices = np.linspace(0, total_rows - 1, MAX_HEATMAP_ROWS, dtype=int)
            sample_df = df.iloc[indices]

        # Build binary matrix: 1 = missing, 0 = present
        null_matrix = sample_df.isnull().astype(int).values.tolist()

        return MissingMatrix(
            columns=list(df.columns),
            data=null_matrix,
            total_rows=total_rows,
            sampled_rows=len(sample_df)
        )
    except Exception as e:
        logger.warning(f"_compute_missing_matrix failed: {e}")
        return None


def _compute_histograms(df: pd.DataFrame) -> Optional[List[ColumnHistogram]]:
    """
    Computes histogram bin counts for all numeric columns using numpy.
    Returns a list of ColumnHistogram objects (one per numeric column).
    WHY BINS? Sending raw data points is O(N×M). Pre-binning reduces it to
    O(20×M_numeric) regardless of dataset size.
    """
    try:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            return []

        histograms = []
        for col_name in numeric_cols:
            col_data = df[col_name].dropna()
            if len(col_data) == 0:
                continue

            # numpy histogram: returns (counts, bin_edges)
            counts, bin_edges = np.histogram(col_data, bins=HISTOGRAM_BINS)

            bins = []
            for i in range(len(counts)):
                bins.append(HistogramBin(
                    bin_start=round(float(bin_edges[i]), 4),
                    bin_end=round(float(bin_edges[i + 1]), 4),
                    count=int(counts[i])
                ))

            histograms.append(ColumnHistogram(
                column_name=col_name,
                bins=bins
            ))

        return histograms
    except Exception as e:
        logger.warning(f"_compute_histograms failed: {e}")
        return None


def _compute_correlation_matrix(df: pd.DataFrame) -> Optional[CorrelationMatrix]:
    """
    Computes Pearson correlation matrix for all numeric columns.
    Returns column names + 2D matrix of correlation coefficients.
    WHY SERVER-SIDE? Computing correlations on 1M rows in-browser is infeasible.
    The backend returns only the N×N matrix (where N = number of numeric columns).
    """
    try:
        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.shape[1] < 2:
            return None  # Need at least 2 numeric columns for correlation

        # Limit to 30 columns max to prevent huge payloads
        if numeric_df.shape[1] > 30:
            numeric_df = numeric_df.iloc[:, :30]

        corr = numeric_df.corr(method='pearson')

        # Replace NaN with None for JSON serialization
        matrix = []
        for _, row in corr.iterrows():
            matrix.append([
                round(float(v), 4) if pd.notna(v) else None
                for v in row
            ])

        return CorrelationMatrix(
            columns=list(corr.columns),
            matrix=matrix
        )
    except Exception as e:
        logger.warning(f"_compute_correlation_matrix failed: {e}")
        return None


def _build_column_profile_polars(df_pl: pl.DataFrame, column_name: str) -> dict:
    """Builds a stats profile dict using Polars — the fast-path for /analyze."""
    col = df_pl[column_name]
    dtype_str = str(col.dtype)
    total_rows = len(df_pl)
    missing_values = col.null_count()
    missing_percentage = round((missing_values / total_rows) * 100, 2) if total_rows > 0 else 0
    unique_values_count = col.n_unique()

    # Map Polars dtypes to Pandas-compatible strings for the rule engine
    dtype_map = dtype_str
    if col.dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                     pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
        dtype_map = 'int64'
    elif col.dtype in (pl.Float32, pl.Float64):
        dtype_map = 'float64'
    elif col.dtype == pl.Utf8 or col.dtype == pl.String:
        dtype_map = 'object'
    elif col.dtype in (pl.Date, pl.Datetime):
        dtype_map = 'datetime64'

    profile = {
        'column_name': column_name,
        'data_type': dtype_map,
        'missing_percentage': float(missing_percentage),
        'unique_values_count': int(unique_values_count),
        'total_rows': int(total_rows)
    }

    # Numeric stats via Polars
    is_numeric = col.dtype in (pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32,
                               pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)
    if is_numeric:
        try:
            non_null = col.drop_nulls().cast(pl.Float64)
            if len(non_null) > 1:
                # Polars has no built-in skew — compute manually
                m = non_null.mean()
                s = non_null.std()
                if s is not None and s > 0 and m is not None:
                    skew = float(((non_null - m) / s).pow(3).mean())
                    profile['skewness'] = skew
                else:
                    profile['skewness'] = None
            else:
                profile['skewness'] = None
        except Exception:
            profile['skewness'] = None

        profile['mean'] = _safe_scalar(col.mean())
        profile['median'] = _safe_scalar(col.median())
        profile['std_dev'] = _safe_scalar(col.std())
        profile['min'] = _safe_scalar(col.min())
        profile['max'] = _safe_scalar(col.max())

    # Data sample — top 10 most frequent non-null values
    try:
        non_null = col.drop_nulls()
        if len(non_null) > 0:
            counts = non_null.value_counts().sort(by="count", descending=True).head(10)
            profile['data_sample'] = [str(v) for v in counts[column_name].to_list()]
        else:
            profile['data_sample'] = []
    except Exception:
        profile['data_sample'] = []

    return profile


def _build_rule_based_analysis(profile: dict) -> dict:
    """Pure rule-based analysis for a column. Returns suggestions, recommended_action, is_problematic."""
    data_type = profile['data_type']
    missing_pct = profile['missing_percentage']
    unique_count = profile['unique_values_count']

    suggestions = ["no_action", "drop_column"]
    recommended_action = "no_action"
    is_problematic = False

    # FIX: Detect constant columns (like all FALSE)
    if unique_count <= 1:
        is_problematic = True
        recommended_action = "drop_column"
        suggestions.insert(0, "drop_column")

    if missing_pct > 0:
        is_problematic = True
        if "drop_missing_rows" not in suggestions:
            suggestions.append("drop_missing_rows")
        if data_type in ('int64', 'float64') or profile.get('mean') is not None:
            skewness = profile.get('skewness')
            if skewness is not None:
                if recommended_action == "no_action" or recommended_action == "drop_column":
                    recommended_action = "impute_median" if abs(skewness) > 1 else "impute_mean"
            else:
                if recommended_action == "no_action" or recommended_action == "drop_column":
                    recommended_action = "impute_mean"
            suggestions.extend(["impute_mean", "impute_median", "impute_knn", "impute_iterative"])
        else:
            if recommended_action == "no_action" or recommended_action == "drop_column":
                recommended_action = "impute_mode"
            suggestions.append("impute_mode")

    if data_type == 'object':
        suggestions.extend(["to_lowercase", "to_uppercase", "trim_whitespace",
                            "remove_special_characters", "convert_to_datetime", "convert_to_numeric"])
        if 1 < unique_count <= 50:
            suggestions.extend(["one_hot_encode", "label_encode"])
            if recommended_action == "no_action":
                recommended_action = "one_hot_encode"

    if profile.get('mean') is not None:  # numeric column
        if profile.get('std_dev', -1) == 0:
            is_problematic = True
            recommended_action = "drop_column"
            if suggestions[0] != "drop_column":
                suggestions.insert(0, "drop_column")
        suggestions.extend(["scale_standard", "scale_minmax", "transform_log", "handle_outliers_iqr"])

    if 'datetime' in data_type:
        suggestions.extend(['extract_year', 'extract_month', 'extract_day', 'extract_day_of_week'])

    return {
        'suggestions': list(dict.fromkeys(suggestions)),
        'recommended_action': recommended_action,
        'is_problematic': is_problematic
    }


async def analyze_all_columns_with_ai(
    df_pl: pl.DataFrame,
    objective: Optional[str] = None,
    model_type: Optional[str] = None
) -> List[ColumnAnalysis]:
    """
    Batched analysis using POLARS for profiling → single Gemini call → merge results.
    Accepts a Polars DataFrame for high-performance column profiling.
    Now accepts optional objective/model_type for context-aware AI guidance.
    """
    # Step 1: Build profiles using Polars and rule-based analysis
    profiles = []
    rule_results = {}
    for col_name in df_pl.columns:
        try:
            profile = _build_column_profile_polars(df_pl, col_name)
            profiles.append(profile)
            rule_results[col_name] = _build_rule_based_analysis(profile)
        except Exception as e:
            logger.error(f"Failed to build Polars profile for '{col_name}': {e}")
            profiles.append({'column_name': col_name, 'data_type': 'unknown', 'data_sample': []})
            rule_results[col_name] = {
                'suggestions': ['drop_column'],
                'recommended_action': 'no_action',
                'is_problematic': True
            }

    # Step 2: PII MASKING — sanitize data samples before Gemini sees them
    masked_profiles = mask_column_profiles(profiles)

    # Step 3: Single batched Gemini API call (with masked data + context)
    ai_results = await call_gemini_batch_analysis(masked_profiles, objective, model_type)

    # Step 3: Index AI results by column_name for fast lookup
    ai_lookup = {r.get('column_name', ''): r for r in ai_results}

    # Step 4: Merge rule-based + AI results into ColumnAnalysis objects
    analysis_results = []
    for profile in profiles:
        col_name = profile['column_name']
        rules = rule_results.get(col_name, {})
        ai = ai_lookup.get(col_name, {})

        ai_insight = ai.get('ai_insight')
        ai_recommendation = ai.get('ai_recommendation')

        suggestions = rules.get('suggestions', ['no_action'])
        recommended_action = rules.get('recommended_action', 'no_action')
        is_problematic = rules.get('is_problematic', False)

        # If AI recommends something actionable, override rule-based
        if ai_recommendation and ai_recommendation != 'no_action':
            is_problematic = True
            if ai_recommendation not in suggestions:
                suggestions.insert(0, ai_recommendation)
            recommended_action = ai_recommendation

        analysis_results.append(ColumnAnalysis(
            column_name=col_name,
            data_type=profile.get('data_type', 'unknown'),
            missing_values=int(profile.get('missing_percentage', 0) * profile.get('total_rows', 0) / 100) if profile.get('total_rows', 0) > 0 else 0,
            missing_percentage=float(profile.get('missing_percentage', 0)),
            unique_values=int(profile.get('unique_values_count', 0)),
            suggestions=suggestions,
            recommended_action=recommended_action,
            is_problematic=is_problematic,
            ai_insights=ai_insight,
            ai_recommendation=ai_recommendation
        ))

    return analysis_results


# --- API Endpoints ---

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

@app.post("/auth/login", response_model=LoginResponse)
async def login_user(login_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    try:
        user = AuthOperations.authenticate_user(db=db, username_or_email=login_data.username_or_email, password=login_data.password)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        session = AuthOperations.create_session(db=db, user_id=user.id, user_agent=request.headers.get("User-Agent"), ip_address=request.client.host)

        return LoginResponse(
            user=user,
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
    return current_user

# --- Phase 3: JWT & SSO Endpoints ---

@app.post("/auth/jwt/login", response_model=JWTLoginResponse)
async def jwt_login(login_data: UserLogin, db: Session = Depends(get_db)):
    """NEW Phase 3 flow: Returns a stateless JWT instead of a DB session token."""
    user = AuthOperations.authenticate_user(db=db, username_or_email=login_data.username_or_email, password=login_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Assuming a role attribute/property exists, otherwise default to "user"
    role = getattr(user, 'role', 'user')

    access_token = create_access_token(user_id=user.id, username=user.username, role=role)
    refresh_token = create_refresh_token(user_id=user.id)

    user_response = UserResponse.model_validate(user)
    user_response.role = role

    return JWTLoginResponse(
        user=user_response,
        access_token=access_token,
        refresh_token=refresh_token
    )

from fastapi.responses import RedirectResponse

@app.get("/auth/oauth/{provider}/login")
async def oauth_login(provider: str):
    """Initiates the OAuth2 flow with Google or Microsoft."""
    if provider not in get_available_providers():
        raise HTTPException(status_code=400, detail=f"Provider {provider} is not configured or supported")
    
    auth_url = get_authorization_url(provider)
    if not auth_url:
        raise HTTPException(status_code=500, detail="Failed to generate authorization URL")
        
    return RedirectResponse(url=auth_url)

@app.get("/auth/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str, db: Session = Depends(get_db)):
    """Handles the OAuth2 callback, creates/links user, and issues JWT."""
    user_info = await exchange_code_for_user_info(provider, code)
    if not user_info:
        raise HTTPException(status_code=400, detail="OAuth authentication failed")
        
    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="OAuth provider did not return an email.")

    # 1. Lookup User
    user = db.query(UserModel).filter(UserModel.email == email).first()

    # 2. Create User if not exists
    if not user:
        name_parts = user_info.get("name", "Oauth User").split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        # Generate random password for OAuth users since they login via SSO
        import secrets
        import string
        random_pwd = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(24))
        
        # Use email prefix as username
        base_username = email.split('@')[0]
        username = base_username
        
        # Ensure unique username
        counter = 1
        while db.query(UserModel).filter(UserModel.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1

        user = AuthOperations.create_user(
            db=db, 
            username=username, 
            email=email, 
            password=random_pwd, 
            first_name=first_name, 
            last_name=last_name
        )

    # 3. Create JWT Tokens
    role = getattr(user, 'role', 'user')
    access_token = create_access_token(user_id=user.id, username=user.username, role=role)
    refresh_token = create_refresh_token(user_id=user.id)

    # 4. Redirect to Frontend
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    redirect_uri = f"{frontend_url}/oauth-callback?token={access_token}&refresh={refresh_token}"
    return RedirectResponse(url=redirect_uri)

from services.jwt_auth import require_role

@app.get("/admin/dashboard")
async def get_admin_dashboard(token_payload: dict = Depends(require_role("admin"))):
    """Example RBAC protected route. Only accessible by admins with valid JWTs."""
    return {"message": "Welcome to the Admin Dashboard", "admin_info": token_payload}

@app.get("/health")
async def health_check():
    """System health check including Phase 3 services."""
    return {
        "status": "ok",
        "pii_masking": get_pii_status(),
        "sso": get_sso_status(),
        "database": "connected" if check_database_connection() else "disconnected"
    }

# --- TABULAR (CSV) WORKFLOW ---

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    objective: Optional[str] = Form(None),
    model_type: Optional[str] = Form(None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and analyze a CSV file using Polars for high-performance profiling.
    Accepts optional 'objective' and 'model_type' form fields to drive
    context-aware AI recommendations via dynamic Gemini prompt injection.
    """
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Validate objective/model_type values
    valid_objectives = {None, '', 'eda', 'machine_learning', 'bi_reporting'}
    valid_model_types = {None, '', 'tree_based', 'linear_models', 'deep_learning'}
    if objective not in valid_objectives:
        raise HTTPException(status_code=400, detail=f"Invalid objective: {objective}")
    if model_type not in valid_model_types:
        raise HTTPException(status_code=400, detail=f"Invalid model_type: {model_type}")

    # Normalize empty strings to None
    objective = objective if objective else None
    model_type = model_type if model_type else None

    logger.info(f"Analyzing file '{file.filename}' with objective='{objective}', model_type='{model_type}'")

    storage_path = os.path.join(UPLOAD_DIR_CSV, f"{uuid4().hex}_{file.filename}")
    with open(storage_path, "wb") as f:
        f.write(contents)

    db_file_upload = DatabaseOperations.create_file_upload(db, file.filename, contents, current_user.id, storage_path)

    # --- POLARS: Read CSV with Polars for fast analysis ---
    try:
        # Polars read_csv reads bytes directly — no need for StringIO/decode
        df_pl = pl.read_csv(BytesIO(contents), ignore_errors=True, infer_schema_length=10000)
    except Exception as e:
        logger.error(f"Polars read_csv error: {e}")
        # Fallback to Pandas if Polars fails (e.g., exotic encoding)
        try:
            try:
                content_str = contents.decode('utf-8')
            except UnicodeDecodeError:
                content_str = contents.decode('latin-1')
            df_pd = pd.read_csv(StringIO(content_str))
            df_pl = pl.from_pandas(df_pd)
            logger.info("Fell back to Pandas->Polars conversion for CSV reading.")
        except Exception as e2:
            logger.error(f"Pandas fallback also failed: {e2}")
            raise HTTPException(status_code=400, detail=f"Failed to parse CSV file: {e2}")

    if df_pl.height == 0:
        raise HTTPException(status_code=400, detail="CSV file is empty or could not be parsed")

    row_count = df_pl.height
    col_count = df_pl.width

    # BATCHED: Context-aware Gemini API call using Polars profiling
    analysis_results = await analyze_all_columns_with_ai(df_pl, objective, model_type)

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

        # --- FEATURE 3: SMOTE Application (after all transforms, before stats) ---
        smote_applied = False
        if request.apply_smote and request.target_column:
            target_col = request.target_column
            if target_col in processed_df.columns:
                try:
                    from imblearn.over_sampling import SMOTE

                    # Separate features and target
                    y = processed_df[target_col]
                    X = processed_df.drop(columns=[target_col])

                    # SMOTE requires all-numeric features
                    numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
                    non_numeric_cols = [c for c in X.columns if c not in numeric_cols]

                    if len(numeric_cols) == 0:
                        logger.warning("SMOTE skipped: no numeric feature columns available.")
                    elif y.nunique() < 2:
                        logger.warning("SMOTE skipped: target has fewer than 2 classes.")
                    else:
                        # Use only numeric features for SMOTE
                        X_numeric = X[numeric_cols].fillna(0)

                        # Determine k_neighbors (must be < smallest class count)
                        min_class_count = y.value_counts().min()
                        k_neighbors = min(5, min_class_count - 1)
                        if k_neighbors < 1:
                            k_neighbors = 1

                        smote = SMOTE(random_state=42, k_neighbors=k_neighbors)
                        X_resampled, y_resampled = smote.fit_resample(X_numeric, y)

                        # Rebuild full DataFrame
                        resampled_df = pd.DataFrame(X_resampled, columns=numeric_cols)

                        # For non-numeric columns, fill with most frequent value for new rows
                        for col in non_numeric_cols:
                            original_vals = X[col].values
                            mode_val = X[col].mode()[0] if not X[col].mode().empty else ''
                            extended = list(original_vals) + [mode_val] * (len(y_resampled) - len(original_vals))
                            resampled_df[col] = extended

                        resampled_df[target_col] = y_resampled.values
                        processed_df = resampled_df
                        smote_applied = True

                        logger.info(f"SMOTE applied: {len(X)} rows → {len(processed_df)} rows")

                except ImportError:
                    logger.error("imbalanced-learn not installed. SMOTE skipped.")
                except Exception as smote_e:
                    logger.error(f"SMOTE failed (non-fatal): {smote_e}")
            else:
                logger.warning(f"SMOTE skipped: target column '{target_col}' not found in processed data.")

        # --- "AFTER" ANALYSIS ---
        after_stats = [get_column_stats(processed_df, col) for col in processed_df.columns]

        # --- FEATURE 2: Compute Advanced Visualization Data ---
        try:
            viz_data = VisualizationData(
                missing_matrix_before=_compute_missing_matrix(df),
                missing_matrix_after=_compute_missing_matrix(processed_df),
                histograms_before=_compute_histograms(df),
                histograms_after=_compute_histograms(processed_df),
                correlation_before=_compute_correlation_matrix(df),
                correlation_after=_compute_correlation_matrix(processed_df),
            )
            logger.info("Advanced visualization data computed successfully.")
        except Exception as viz_e:
            logger.warning(f"Visualization data computation failed (non-fatal): {viz_e}")
            viz_data = None

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
            },
            visualization_data=viz_data
        )
        
    except Exception as e:
        logger.error(f"Error during data processing: {e}", exc_info=True)
        if job_id:
            DatabaseOperations.update_processing_job_status(db, job_id, "failed", error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Data processing failed: {str(e)}")

# --- Feature 3: Class Imbalance Detection ---

class ImbalanceCheckRequest(BaseModel):
    file_id: int
    target_column: str

class ImbalanceCheckResponse(BaseModel):
    target_column: str
    class_distribution: Dict[str, int]
    class_percentages: Dict[str, float]
    total_samples: int
    is_imbalanced: bool
    imbalance_severity: str  # "balanced", "moderate", "severe"
    majority_class: str
    minority_class: str
    majority_percentage: float

@app.post("/detect-imbalance", response_model=ImbalanceCheckResponse)
async def detect_class_imbalance(
    request: ImbalanceCheckRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyzes the class distribution of a target column in a previously uploaded file.
    Returns class counts, percentages, and an imbalance severity flag.
    Thresholds:  >80% majority = severe,  >65% majority = moderate,  else = balanced.
    """
    file_record = db.query(FileUpload).filter(
        FileUpload.id == request.file_id,
        FileUpload.user_id == current_user.id
    ).first()
    if not file_record or not file_record.storage_path:
        raise HTTPException(status_code=404, detail="File not found.")

    if not os.path.exists(file_record.storage_path):
        raise HTTPException(status_code=404, detail="File no longer exists on server.")

    try:
        df = pd.read_csv(file_record.storage_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    if request.target_column not in df.columns:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{request.target_column}' not found. Available: {list(df.columns)}"
        )

    col = df[request.target_column].dropna()
    total = len(col)
    if total == 0:
        raise HTTPException(status_code=400, detail="Target column has no non-null values.")

    value_counts = col.value_counts()
    class_dist = {str(k): int(v) for k, v in value_counts.items()}
    class_pcts = {str(k): round(v / total * 100, 2) for k, v in value_counts.items()}

    majority_class = str(value_counts.index[0])
    minority_class = str(value_counts.index[-1])
    majority_pct = float(value_counts.iloc[0] / total * 100)

    # Severity thresholds
    if majority_pct >= 80:
        severity = "severe"
        is_imbalanced = True
    elif majority_pct >= 65:
        severity = "moderate"
        is_imbalanced = True
    else:
        severity = "balanced"
        is_imbalanced = False

    return ImbalanceCheckResponse(
        target_column=request.target_column,
        class_distribution=class_dist,
        class_percentages=class_pcts,
        total_samples=total,
        is_imbalanced=is_imbalanced,
        imbalance_severity=severity,
        majority_class=majority_class,
        minority_class=minority_class,
        majority_percentage=round(majority_pct, 2)
    )

@app.get("/download/job/{job_id}")
async def download_processed_file(job_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Downloads the processed CSV file from a completed job.
    
    WHY NOT response_class=FileResponse?
    We need to set a custom Content-Disposition header with a clean, user-facing
    filename (not the internal UUID-prefixed storage name). Using Response directly
    gives us full control over headers.
    """
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

    # Look up the original filename for a clean download name
    file_record = db.query(FileUpload).filter(FileUpload.id == job.file_upload_id).first()
    original_name = file_record.original_filename if file_record else "dataset"

    # Ensure the download name ends with .csv
    if not original_name.lower().endswith('.csv'):
        original_name = original_name + '.csv'
    download_name = f"cleaned_{original_name}"

    return FileResponse(
        path=file_path,
        filename=download_name,
        media_type='text/csv'
    )

@app.get("/history")
async def get_history(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch user's upload and processing history, including latest job_id for each upload."""
    uploads = DatabaseOperations.get_user_upload_history(db, current_user.id)
    history = []
    for u in uploads:
        # Feature 4: Find the latest completed processing job for this upload
        latest_job = db.query(DataProcessingJob).filter(
            DataProcessingJob.file_upload_id == u.id,
            DataProcessingJob.processing_status == "completed"
        ).order_by(DataProcessingJob.started_at.desc()).first()

        history.append({
            "id": u.id,
            "filename": u.filename,
            "row_count": u.row_count,
            "column_count": u.column_count,
            "upload_timestamp": u.upload_timestamp.isoformat() if u.upload_timestamp else None,
            "status": u.status,
            "latest_job_id": latest_job.id if latest_job else None,
        })
    return {"uploads": history}

@app.get("/analytics")
async def get_analytics(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch usage statistics for the user dashboard."""
    stats = DatabaseOperations.get_usage_statistics(db, days=30, user_id=current_user.id)
    return stats

@app.get("/analysis/{file_id}", response_model=Dict[str, Any])
async def get_historical_analysis(file_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch historical analysis data for a specific file upload to populate UploadPage."""
    file_record = db.query(FileUpload).filter(
        FileUpload.id == file_id,
        FileUpload.user_id == current_user.id
    ).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File upload not found")

    analysis_result = db.query(AnalysisResult).filter(AnalysisResult.file_upload_id == file_id).first()
    if not analysis_result:
        raise HTTPException(status_code=404, detail="Analysis result not found")

    result_data = analysis_result.analysis_data
    result_data["file_id"] = file_id
    if "filename" not in result_data:
        result_data["filename"] = file_record.filename
        
    return result_data


# --- Feature 4: Historical Job Visualization Retrieval ---

@app.get("/analysis/job/{job_id}", response_model=DashboardAnalysisResponse)
async def get_historical_job_analysis(
    job_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the full Before vs. After analysis for a completed processing job.
    Recomputes visualization data from the saved original + processed CSVs on disk.
    WHY RECOMPUTE? Storing full viz payloads (matrices, histograms) in the DB would
    bloat it significantly. The computation is fast (<500ms for most datasets).
    """
    # 1. Find the job — enforces user ownership
    job = db.query(DataProcessingJob).filter(
        DataProcessingJob.id == job_id,
        DataProcessingJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.processing_status != "completed":
        raise HTTPException(status_code=400, detail="Job has not completed processing.")
    if not job.output_filename:
        raise HTTPException(status_code=404, detail="Processed output file not found for this job.")

    # 2. Locate the original file
    file_record = db.query(FileUpload).filter(FileUpload.id == job.file_upload_id).first()
    if not file_record or not file_record.storage_path:
        raise HTTPException(status_code=404, detail="Original file record not found.")
    if not os.path.exists(file_record.storage_path):
        raise HTTPException(status_code=404, detail="Original CSV no longer exists on server.")

    # 3. Locate the processed file
    processed_path = os.path.join(UPLOAD_DIR_CSV, job.output_filename)
    if not os.path.exists(processed_path):
        raise HTTPException(status_code=404, detail="Processed CSV no longer exists on server.")

    # 4. Read both CSVs with Pandas (consistent with /process endpoint)
    try:
        original_df = pd.read_csv(file_record.storage_path)
        processed_df = pd.read_csv(processed_path)
    except Exception as e:
        logger.error(f"Failed to read CSVs for historical job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read CSV files: {e}")

    # 5. Compute before/after column stats
    before_stats = [get_column_stats(original_df, col) for col in original_df.columns]
    after_stats = [get_column_stats(processed_df, col) for col in processed_df.columns]

    # 6. Compute visualization data (same functions used by /process)
    try:
        viz_data = VisualizationData(
            missing_matrix_before=_compute_missing_matrix(original_df),
            missing_matrix_after=_compute_missing_matrix(processed_df),
            histograms_before=_compute_histograms(original_df),
            histograms_after=_compute_histograms(processed_df),
            correlation_before=_compute_correlation_matrix(original_df),
            correlation_after=_compute_correlation_matrix(processed_df),
        )
        logger.info(f"Historical viz data computed for job {job_id}")
    except Exception as viz_e:
        logger.warning(f"Historical viz data computation failed for job {job_id}: {viz_e}")
        viz_data = None

    return DashboardAnalysisResponse(
        job_id=job_id,
        analysis={
            "before": [s.dict() for s in before_stats],
            "after": [s.dict() for s in after_stats]
        },
        visualization_data=viz_data,
        filename=file_record.original_filename
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
                        
                        # Fix: Ensure file extension matches actual format to prevent "incorrect format" errors
                        ext = ".png" if save_format == "PNG" else ".jpg"
                        base_name = filename.rsplit('.', 1)[0]
                        new_filename = f"{base_name}{ext}"
                        
                        processed_zip.writestr(new_filename, buffer.getvalue())
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

# --- Duplicate endpoint definitions removed (were shadowed by earlier registrations) ---

if __name__ == "__main__":
    import uvicorn
    # This block is for running directly (e.g., python main.py)
    # uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    # Note: The 'app' object must be available, so we just run uvicorn as a command
    pass