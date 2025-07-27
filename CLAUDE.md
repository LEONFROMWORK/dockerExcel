# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Excel Unified is an AI-powered Excel knowledge platform that combines:
- **Excel File Analysis**: Error detection, formula validation, VBA analysis
- **AI Consultation**: Real-time chat with GPT-4 for Excel problem solving
- **Knowledge Base**: Vector search for similar problems and solutions
- **Image-to-Excel**: OCR capabilities for converting images/PDFs to Excel

### Tech Stack
- **Backend**: Rails 8.0.2 with PostgreSQL + pgvector
- **Frontend**: Vue.js 3 with Vite, Pinia, Vue Router
- **Python Service**: FastAPI for AI/ML processing (port 8000)
- **Styling**: Tailwind CSS with shadcn/ui components
- **Background Jobs**: Sidekiq with Redis
- **Excel Processing**: ExcelJS + HyperFormula (frontend), openpyxl + pandas (backend)

## Key Commands

### Development Setup
```bash
# Rails app
cd rails-app
bundle install
npm install
bin/rails db:create db:migrate db:seed
bin/dev  # Starts Rails, Vite, and Tailwind

# Python service
cd python-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Run both services
cd rails-app && bin/dev  # Terminal 1
cd python-service && uvicorn main:app --reload  # Terminal 2
```

### Testing
```bash
# Rails tests
cd rails-app
bundle exec rspec  # All specs
bundle exec rspec spec/domains/excel_analysis  # Domain-specific
COVERAGE=true bundle exec rspec  # With coverage

# JavaScript tests
npm test  # Run Vitest
npm run test:coverage  # With coverage

# Python tests
cd python-service
pytest
pytest tests/test_advanced_vba_analyzer.py  # Single test
```

### Docker & Deployment
```bash
# Docker development
docker-compose up
docker-compose exec web rails console
docker-compose exec web rails db:migrate

# Railway deployment
railway login
railway up
railway logs
railway run rails console
```

### Code Quality
```bash
cd rails-app
bin/rubocop  # Ruby linting
npm run lint  # JavaScript linting
bin/brakeman  # Security scan
```

## Architecture

### Domain-Driven Design
```
rails-app/app/domains/
├── authentication/     # User auth, OAuth, sessions
├── excel_analysis/     # Excel processing, error detection
├── ai_consultation/    # Chat, AI integration
├── knowledge_base/     # Q&A, vector search
└── data_pipeline/      # Admin data collection

Each domain contains:
├── controllers/
├── models/
├── repositories/
├── services/
└── errors/
```

### Frontend Organization
```
rails-app/app/javascript/
├── domains/           # Domain-specific components
│   ├── excel_ai/     # Excel AI assistant
│   └── account/      # User account
├── components/       # Shared UI components
├── composables/      # Vue composables
├── stores/          # Pinia stores
├── services/        # API clients
└── utils/           # Helpers
```

### Service Communication
- Rails → Python: HTTP via `PYTHON_SERVICE_URL` (default: http://localhost:8000)
- Python → Rails: HTTP via `RAILS_API_URL`
- Frontend → Rails: `/api/v1/*` endpoints
- Frontend → Python: Proxied through Rails

### Key Services

**Rails Services** (inherit from ApplicationService):
- `ExcelAnalysis::FileAnalysisService` - Excel file processing
- `AiConsultation::ChatService` - AI chat management
- `KnowledgeBase::SearchService` - Vector similarity search
- `Authentication::OauthService` - Google OAuth handling

**Python Services**:
- `advanced_vba_analyzer.py` - VBA error detection (95.3% accuracy)
- `ai_excel_generator.py` - AI-powered Excel generation
- `multilingual_ocr_service.py` - Image to Excel conversion
- `openai_service.py` - GPT-4 integration

### Database Schema

Key tables with vector search:
- `users` - Authentication and profiles
- `excel_files` - Uploaded Excel files
- `excel_analyses` - Analysis results
- `qa_pairs` - Knowledge base with embeddings
- `chat_sessions` - AI consultation history

Vector search example:
```ruby
QaPair.nearest_neighbors(:embedding, query_embedding, distance: "cosine")
      .limit(5)
```

## Environment Variables

### Required
```bash
# Rails
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
PYTHON_SERVICE_URL=http://localhost:8000

# Python
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://...
RAILS_API_URL=http://localhost:3000
```

### Optional
```bash
REDIS_URL=redis://localhost:6379
SIDEKIQ_CONCURRENCY=5
FORCE_SSL=true  # Production only
```

## Development Patterns

### Service Objects
```ruby
class ExcelAnalysis::FileAnalysisService < ApplicationService
  def call(file)
    validate_file!(file)
    analysis = perform_analysis(file)
    Result.success(data: analysis)
  rescue => e
    Result.failure(error: e.message)
  end
end
```

### Repository Pattern
```ruby
class ExcelAnalysis::ExcelFileRepository < ApplicationRepository
  def find_by_user(user)
    excel_files.where(user: user).order(created_at: :desc)
  end
end
```

### Frontend API Calls
```javascript
// Using apiClient utility
import { apiClient } from '@/utils/apiClient'

const response = await apiClient.post('/api/v1/excel/analyze', {
  file_id: fileId
})
```

### Error Handling
- Backend: `Result` objects with success/failure states
- Frontend: Try-catch with toast notifications
- Python: FastAPI exception handlers with proper status codes

## Performance Considerations

### Frontend
- Lazy loading for routes and heavy components
- ExcelJS + HyperFormula for client-side Excel processing
- LRU cache for Excel data
- Virtual scrolling for large datasets

### Backend
- N+1 query prevention with `includes`
- Background jobs for heavy processing
- Redis caching for frequent queries
- Connection pooling for Python service

### Excel Processing
- Client-side for files < 10MB
- Server-side for larger files or complex analysis
- Streaming for very large files
- Chunked processing in background jobs