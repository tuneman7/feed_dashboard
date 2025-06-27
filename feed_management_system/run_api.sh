#!/bin/bash
# Activate virtual environment and run FastAPI
source venv/bin/activate
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
