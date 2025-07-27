# Excel AI Python Service

FastAPI-based AI service for Excel analysis and consultation.

## Features

- Excel file analysis with AI insights
- Vector-based semantic search
- AI-powered Excel problem solving
- Real-time chat consultation
- Formula validation and explanation

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy environment configuration:
```bash
cp .env.example .env
```

4. Update `.env` with your configuration:
- Set `OPENAI_API_KEY` with your OpenAI API key
- Update database connection if needed
- Configure other settings as required

## Running the Service

### Local Development
```bash
uvicorn main:app --reload
```

### Using Docker
```bash
docker-compose up
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Health Check
- `GET /api/v1/health/status` - Basic health check
- `GET /api/v1/health/detailed` - Detailed health with system info
- `GET /api/v1/health/ready` - Readiness probe

### Excel Analysis
- `POST /api/v1/excel/analyze` - Analyze Excel file
- `POST /api/v1/excel/extract-formulas` - Extract all formulas
- `POST /api/v1/excel/validate-formula` - Validate and explain formula

### AI Consultation
- `POST /api/v1/ai/chat` - Chat completion for Excel queries
- `POST /api/v1/ai/solve-problem` - Generate solution for Excel problem
- `POST /api/v1/ai/analyze-image` - Analyze Excel screenshot

### Embeddings & Search
- `POST /api/v1/embeddings/generate` - Generate text embedding
- `POST /api/v1/embeddings/index-document` - Index document with embedding
- `POST /api/v1/embeddings/search` - Search similar documents
- `PUT /api/v1/embeddings/update-document/{id}` - Update document embedding
- `DELETE /api/v1/embeddings/document/{id}` - Delete document embedding

## Testing

Run tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app tests/
```

## Development

### Code Formatting
```bash
black app/
```

### Linting
```bash
flake8 app/
```

### Type Checking
```bash
mypy app/
```

## Deployment

The service is designed to be deployed on Railway alongside the Rails application.

### Railway Deployment

1. Create a new Railway service for Python
2. Set environment variables in Railway dashboard
3. Deploy using Railway CLI or GitHub integration

### Environment Variables Required

- `OPENAI_API_KEY` - OpenAI API key
- `DATABASE_URL` - PostgreSQL connection string
- `RAILS_API_URL` - URL of Rails API
- `RAILS_API_KEY` - Authentication key for Rails API

## Architecture

The service follows a clean architecture pattern:

```
app/
├── api/          # API endpoints
├── core/         # Core configuration and utilities
├── models/       # Database models
├── services/     # Business logic services
└── utils/        # Utility functions
```

## Integration with Rails

This service integrates with the Rails application for:
- Receiving Excel files for analysis
- Providing AI insights for chat sessions
- Managing vector embeddings for search
- Enhancing knowledge base with AI capabilities