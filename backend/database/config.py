# File: backend/database/config.py
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import logging

# --- FIX 1: Import the one, true Base from your models file ---
from .models import Base 

logger = logging.getLogger(__name__)

# Get the absolute path to the directory containing this config.py file
current_dir = os.path.dirname(os.path.abspath(__file__))

# Define the path to your database file.
DATABASE_FILE_PATH = os.path.join(current_dir, '..', 'dataspark.db')

# Update DATABASE_URL to use the absolute path
DATABASE_URL = f"sqlite:///{DATABASE_FILE_PATH}"

# Create engine with SQLite-specific settings
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # Allow multiple threads to access the same connection
        "timeout": 20                # 20 second timeout for database locks
    },
    poolclass=StaticPool, # Use StaticPool for SQLite with check_same_thread=False
    echo=False  # Set to True for SQL debugging (useful for seeing queries)
)

# Create SessionLocal class - this is your factory for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- FIX 2: We have REMOVED the line "Base = declarative_base()" from here ---
# The correct Base is now imported from models.py

# Dependency to get a database session for FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback() # Rollback changes on error
        raise # Re-raise the exception
    finally:
        db.close() # Always close the session

# Health check function
def check_database_connection():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

# Function to initialize database tables
def init_database():
    try:
        # This function now uses the correct Base object imported from models.py,
        # which contains the metadata for all your tables.
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False

