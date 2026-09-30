import os
import uvicorn

# ==========================================
# LOCAL DEVELOPMENT OVERRIDE
# ==========================================
# This script is used to run the application locally WITHOUT Docker.
# It overrides the database to use a local SQLite file and disables Redis.

# 1. Force the app to use SQLite instead of PostgreSQL
os.environ["DATABASE_URL"] = "sqlite:///./local_dev.db"

# 2. Force Celery to execute tasks synchronously in-memory (No Redis needed)
from app.worker import celery
celery.conf.task_always_eager = True
celery.conf.task_eager_propagates = True

if __name__ == "__main__":
    print("\n" + "="*50)
    print("Starting EVE Healthcare in LOCAL DEV MODE")
    print("Database: SQLite (local_dev.db)")
    print("Background Tasks: Synchronous (No Redis)")
    print("="*50 + "\n")
    
    # Run the FastAPI application with auto-reload enabled
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
