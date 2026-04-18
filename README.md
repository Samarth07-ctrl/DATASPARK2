# ⚡ DataSpark 2.0: Enterprise AI Preprocessing Engine

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Stop wrangling. Start modeling.** > DataSpark 2.0 is an intelligent, multimodal data preprocessing platform that eliminates the "80/20 data janitor bottleneck." It automatically transforms raw, messy tabular and image datasets into secure, machine-learning-ready pipelines in seconds.

---

## 🌟 The Vision

In enterprise ML, the most sophisticated model will fail if trained on dirty data. Furthermore, feeding sensitive corporate data into external LLMs creates massive privacy risks. 

DataSpark 2.0 bridges this gap. It acts as an **AI Co-Pilot for Data Engineering**, combining blazing-fast multi-threaded processing with military-grade PII masking, ensuring your data is clean, balanced, and strictly compliant before a model ever sees it.

---

## ✨ Enterprise-Grade Features

| Capability | Description | Technical Implementation |
| :--- | :--- | :--- |
| **🚀 High-Speed Ingestion** | Handles massive datasets without memory crashes. | Migrated from Pandas to **Polars** for multi-threaded, lazy-evaluated DataFrame processing. |
| **🛡️ Zero-Trust AI Privacy** | Scans and redacts sensitive data (SSNs, Emails, CCs) *before* it leaves your server. | Powered by **Microsoft Presidio** and Spacy NLP pipelines. |
| **🧠 Context-Aware AI** | Adapts cleaning recommendations based on your end goal (e.g., skips scaling for XGBoost, enforces it for Neural Nets). | Integrated **Google Gemini 2.5 Flash** with dynamic system prompting. |
| **⚖️ Automated SMOTE** | Detects severe class imbalances in target variables and offers instant synthetic over-sampling. | Utilizes **imbalanced-learn** to prevent skewed fraud/anomaly models. |
| **📊 Advanced Analytics** | Data-scientist-grade visual reports (Missing Values Heatmaps, Distribution Histograms, Correlation Matrices). | Computed via backend Polars; rendered interactively via **Recharts**. |
| **🔐 Secure Access (SSO)** | Stateless, scalable authentication built for enterprise teams. | Fully implemented **JWT Access/Refresh Tokens** and **Google OAuth 2.0**. |

---

## 🏗️ System Architecture

DataSpark 2.0 utilizes a decoupled, API-first architecture designed for scale.

### The Technology Stack
* **Frontend:** React 19, React Router v7, Recharts (Dark-themed SPA)
* **Backend:** FastAPI (ASGI), Uvicorn, Pydantic v2
* **Data Processing Engine:** Polars, NumPy, PyArrow
* **Machine Learning Prep:** Scikit-learn (IterativeImputer, StandardScaler), Imbalanced-learn (SMOTE)
* **Security & Compliance:** Microsoft Presidio (PII), Bcrypt, OAuthlib
* **Infrastructure:** Docker, Nginx, Docker Compose

---

## 🚀 Getting Started

Follow these steps to set up and run the DataSpark 2.0 platform locally on your machine:

```bash
# 1. Clone the repository
git clone [https://github.com/Samarth07-ctrl/DATASPARK2.git](https://github.com/Samarth07-ctrl/DATASPARK2.git)
cd DATASPARK2

# 2. Set up the Backend (FastAPI)
cd backend
python -m venv venv
source venv/bin/activate   # Note: On Windows, use `.\venv\Scripts\activate`
pip install -r requirements.txt
cp .env.example .env       # (Remember to add your API keys to this new .env file)
python create_db.py
cd ..

# 3. Set up the Frontend (React)
cd frontend
npm install
cp .env.example .env       
cd ..

echo "✅ Setup Complete!"
echo "To start the platform, open two terminals:"
echo "Terminal 1: cd backend && source venv/bin/activate && uvicorn main:app --reload"
echo "Terminal 2: cd frontend && npm start"
