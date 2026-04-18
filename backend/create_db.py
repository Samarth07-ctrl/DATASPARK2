import os
import logging
from database.config import init_database, DATABASE_FILE_PATH, check_database_connection
from database.models import Base # Make sure all models are imported via Base

# Set up a simple logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_database():
    """
    Initializes the database.
    - Deletes the old database file if it exists.
    - Creates all new tables from the models.
    - Verifies the connection.
    """
    
    # 1. Delete the old database file to ensure a clean schema
    if os.path.exists(DATABASE_FILE_PATH):
        try:
            os.remove(DATABASE_FILE_PATH)
            logger.info(f"Removed old database file: {DATABASE_FILE_PATH}")
        except Exception as e:
            logger.error(f"Could not remove old database file: {e}")
            return

    # 2. Initialize the database and create tables
    logger.info("Initializing new database and creating tables...")
    if init_database():
        logger.info("Database tables created successfully.")
    else:
        logger.error("Failed to create database tables.")
        return

    # 3. Verify the connection
    logger.info("Verifying database connection...")
    if check_database_connection():
        logger.info("Database connection verified. Setup complete.")
    else:
        logger.error("Failed to connect to the new database.")

if __name__ == "__main__":
    setup_database()