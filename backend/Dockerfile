# ==============================================================================
# Backend Dockerfile — Multi-stage production build
# ==============================================================================
# WHY multi-stage? The builder stage installs all build dependencies (gcc, etc.)
# needed by some pip packages. The final stage copies only the installed packages,
# resulting in a much smaller image (~200MB vs ~800MB).
# ==============================================================================

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies for packages like bcrypt, scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Final Stage ---
FROM python:3.11-slim

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create directories for file storage
RUN mkdir -p uploaded_csv_files uploaded_image_datasets processed_csv_files

# Expose the FastAPI port
EXPOSE 8000

# Run with uvicorn — 4 workers for production concurrency
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
