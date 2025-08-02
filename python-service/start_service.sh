#\!/bin/bash

# Load environment variables from .env file
export $(grep -v "^#" .env | xargs)

# Start the Python service with loaded environment variables  
uvicorn main:app --reload --port 8000 --host 0.0.0.0
