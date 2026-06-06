# DataSpark 2.0 ✨

DataSpark 2.0 is an enterprise-grade, high-performance data processing and AI analytics platform designed to automate Data Science workflows. It seamlessly merges advanced machine learning operations with an intuitive dashboard, allowing users to sanitize datasets, detect class imbalances, run context-aware AI analyses, and visualize feature distributions—all in seconds.

## 🚀 Key Features

*   **Intelligent Data Preprocessing:** Upload raw datasets (CSV) and let the engine automatically fix missing values, prune outliers, drop constant columns, and standardize formatting (date parsing, lowercase normalization, currency stripping).
*   **Context-Aware AI Guidance (Gemini Integration):** The backend leverages the Google Gemini API to scan dataset schemas and distribute highly tailored, context-specific recommendations based on your analytical objectives (e.g., ML modeling, BI reporting).
*   **Advanced Image Processing Workflow:** Upload ZIP archives of images and dynamically execute bulk resizing, grayscale conversion, Gaussian blur, and contrast adjustments in the background.
*   **Machine Learning Priming (SMOTE):** Built-in class imbalance detection. If a target variable suffers from severe imbalance, the platform automatically applies SMOTE to oversample the minority class prior to analytics.
*   **High-Fidelity Visualizations:** Before & After interactive dashboards powered by Recharts, offering deep insights through Missing Values Heatmaps, Correlation Matrices, and Distribution Histograms.
*   **Robust Authentication & Security:** Enterprise SSO (Google) integration with secure stateless JWT access tokens, paired with PII (Personally Identifiable Information) masking to ensure sensitive data is removed before AI analysis.

## 🛠️ Technology Stack

**Backend**
*   **FastAPI & Uvicorn**: High-concurrency Python ASGI framework.
*   **Polars & Pandas**: Hyper-fast DataFrame manipulation and profiling.
*   **Scikit-Learn & Imbalanced-Learn**: Core ML libraries for scaling, imputation, and SMOTE implementation.
*   **SQLAlchemy & SQLite**: ORM for storing historical usage, schemas, and processed state.
*   **Google Gemini API**: Batched inference for real-time dataset recommendations.
*   **PyJWT**: Secure OAuth2 callback and token management.

**Frontend**
*   **React 18 & React Router**: Dynamic, SPA (Single Page Application) interactions via Context API.
*   **Tailwind CSS & Lucide Icons**: A premium, "glassmorphism" aesthetic with a tailored dark mode and smooth micro-animations.
*   **Recharts**: Performant SVG-based data visualizations.

## ⚙️ Getting Started

### Prerequisites
*   Node.js (v16+)
*   Python (3.9+)
*   A Google Gemini API Key

### Backend Setup
1. Navigate to the `backend` directory.
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the `.env.example` to `.env` and fill out your variables (e.g., `GEMINI_API_KEY`).
4. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```
   *(Server defaults to `http://localhost:8000`)*

### Frontend Setup
1. Navigate to the `frontend` directory.
2. Install Node dependencies:
   ```bash
   npm install
   ```
3. Start the React development server:
   ```bash
   npm start
   ```
   *(App defaults to `http://localhost:3000`)*

## 📂 Project Structure
*   `/backend/main.py`: Core routing and API aggregation logic.
*   `/backend/services/`: Specific standalone logics (`pii_masking`, `jwt_auth`, `oauth_sso`).
*   `/frontend/src/pages/`: Main application workflows (`AnalysisDashboard`, `UploadPage`, `ImageProcessing`).

## 🛡️ License
This project is licensed under the MIT License.
