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
- **Excel Processing**: HyperFormula (frontend formulas), openpyxl + pandas (backend)
- **Spreadsheet UI**: Univer for Excel-like interface

## Key Commands

### Development Setup
```bash
# Initial setup (Ruby, JS dependencies, DB)
cd rails-app && bin/setup

# Rails app (includes Vite and Tailwind)
cd rails-app && bin/dev

# Python service
cd python-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
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
bundle exec rspec                          # All specs
bundle exec rspec spec/domains/excel_analysis  # Domain-specific
bundle exec rspec spec/services/advanced_vba_analyzer_spec.rb:45  # Single test line
COVERAGE=true bundle exec rspec            # With coverage
CHROME_HEADLESS=false bundle exec rspec    # Show browser

# JavaScript tests
cd rails-app
npm test                    # Run Vitest
npm run test:ui            # Vitest UI
npm run test:coverage      # With coverage

# Python tests
cd python-service
pytest                                      # All tests
pytest tests/test_advanced_vba_analyzer.py  # Single file
pytest -k "test_analyze_vba"               # Match test name
pytest -m "slow"                           # Run marked tests

# E2E tests
cd rails-app
npx cypress open           # Interactive mode
npx cypress run           # Headless mode
```

### Code Quality
```bash
cd rails-app
bin/rubocop               # Ruby linting
bin/rubocop -a           # Auto-fix issues
bin/brakeman             # Security scan
npm run lint             # JavaScript linting
bin/bundle-audit check   # Gem vulnerabilities
```

### Docker & Deployment
```bash
# Docker development
docker-compose up
docker-compose exec web rails console
docker-compose exec web rails db:migrate
docker-compose exec python python

# Railway deployment
railway login
railway up
railway logs
railway run rails console
railway variables          # View env vars

# Production build
docker build -f Dockerfile.prod -t excel-unified .
```

### Useful Development Scripts
```bash
cd rails-app
bin/rails console         # Rails console
bin/rails dbconsole      # Database console
bin/importmap pin <pkg>  # Add JS package
bin/deploy              # Deploy to production
bin/remote-console      # Production Rails console
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
├── serializers/
├── value_objects/
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
- WebSocket: Action Cable for real-time features

### Key Services

**Rails Services** (inherit from ApplicationService):
- `ExcelAnalysis::FileAnalysisService` - Excel file processing
- `ExcelAnalysis::ErrorDetectionService` - Find Excel errors
- `AiConsultation::ChatService` - AI chat management
- `KnowledgeBase::SearchService` - Vector similarity search
- `Authentication::OauthService` - Google OAuth handling

**Python Services**:
- `advanced_vba_analyzer.py` - VBA error detection (95.3% accuracy)
- `ai_excel_generator.py` - AI-powered Excel generation
- `multilingual_ocr_service.py` - Image to Excel conversion
- `openai_service.py` - GPT-4 integration
- `excel_processor.py` - Main Excel file processing
- `ai_failover_service.py` - Multi-provider AI failover

### Database Schema

Key tables with vector search:
- `users` - Authentication and profiles
- `excel_files` - Uploaded Excel files
- `excel_analyses` - Analysis results with JSON details
- `qa_pairs` - Knowledge base with embeddings
- `chat_sessions` - AI consultation history
- `chat_messages` - Individual chat messages
- `vba_analyses` - VBA code analysis results

Vector search example:
```ruby
QaPair.nearest_neighbors(:embedding, query_embedding, distance: "cosine")
      .limit(5)
```

## Environment Variables

### Required
```bash
# Rails
DATABASE_URL=postgresql://user:pass@localhost/excel_unified_dev
OPENAI_API_KEY=sk-...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
PYTHON_SERVICE_URL=http://localhost:8000
SECRET_KEY_BASE=...  # Use: rails secret

# Python
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://user:pass@localhost/excel_unified_dev
RAILS_API_URL=http://localhost:3000
RAILS_INTERNAL_API_KEY=...  # Must match Rails
```

### Optional
```bash
REDIS_URL=redis://localhost:6379
SIDEKIQ_CONCURRENCY=5
FORCE_SSL=true  # Production only
ACTION_CABLE_ALLOWED_REQUEST_ORIGINS=http://localhost:3000
ANTHROPIC_API_KEY=...  # For Claude failover
GROQ_API_KEY=...      # For Groq failover
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

# Usage
result = ExcelAnalysis::FileAnalysisService.call(file)
if result.success?
  analysis = result.data
else
  handle_error(result.error)
end
```

### Repository Pattern
```ruby
class ExcelAnalysis::ExcelFileRepository < ApplicationRepository
  def find_with_analyses(id)
    excel_files
      .includes(:excel_analyses, :user)
      .find(id)
  end

  private

  def excel_files
    ExcelAnalysis::ExcelFile.all
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

// With error handling
try {
  const { data } = await apiClient.get('/api/v1/excel/files')
  // Process data
} catch (error) {
  toast.error(error.message)
}
```

### Vue Composables
```javascript
// Domain-specific composable
import { useUnifiedExcelAI } from '@/domains/excel_ai/composables/useUnifiedExcelAI'

const { 
  currentFile, 
  isProcessing, 
  uploadFile,
  analyzeFile 
} = useUnifiedExcelAI()
```

## Performance Considerations

### Frontend
- Lazy loading for routes and heavy components
- HyperFormula for client-side formula calculations only
- LRU cache for Excel data (lru-cache package)
- Virtual scrolling in Univer for large datasets
- Dynamic imports for code splitting

### Backend
- N+1 query prevention with `includes` and `preload`
- Background jobs (Sidekiq) for heavy processing
- Redis caching for frequent queries
- Connection pooling for Python service
- Database indexes on foreign keys and search fields

### Excel Processing
- Server-side processing for all Excel files
- Streaming for very large files
- Chunked processing in background jobs
- Client-side formula evaluation with HyperFormula
- File size limits enforced at multiple levels

## Testing Strategies

### RSpec Best Practices
```ruby
# Use proper test data setup
let(:user) { create(:user) }
let(:excel_file) { create(:excel_file, :with_errors, user: user) }

# Test service objects
it "analyzes Excel file successfully" do
  result = described_class.call(excel_file)
  expect(result).to be_success
  expect(result.data[:errors]).to be_present
end

# Use shared examples for common behaviors
it_behaves_like "authenticated endpoint"
```

### Frontend Testing
```javascript
// Test with Testing Library
import { render, screen, fireEvent } from '@testing-library/vue'
import { createTestingPinia } from '@pinia/testing'

test('uploads file successfully', async () => {
  const { getByLabelText } = render(Component, {
    global: {
      plugins: [createTestingPinia()]
    }
  })
  
  const file = new File(['test'], 'test.xlsx')
  const input = getByLabelText('Upload Excel file')
  await fireEvent.update(input, { target: { files: [file] } })
  
  expect(screen.getByText('Analyzing...')).toBeInTheDocument()
})
```

## Troubleshooting

### Common Issues

1. **PostgreSQL pgvector extension**
   ```sql
   -- Enable in database
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **Python service connection errors**
   - Ensure Python service is running on port 8000
   - Check PYTHON_SERVICE_URL in Rails .env
   - Verify CORS settings in Python service

3. **Redis connection (development)**
   ```bash
   # macOS
   brew services start redis
   # Linux
   sudo systemctl start redis
   ```

4. **Asset compilation issues**
   ```bash
   cd rails-app
   rm -rf tmp/cache
   bin/rails assets:clobber
   bin/rails assets:precompile
   ```

5. **Database migration conflicts**
   ```bash
   bin/rails db:rollback STEP=1
   # Fix migration file
   bin/rails db:migrate
   ```

## Security Best Practices

1. **API Keys**: Never commit to repository
2. **File Uploads**: Validated and scanned
3. **SQL Injection**: Use parameterized queries
4. **XSS Protection**: DOMPurify for user content
5. **CORS**: Configured per environment
6. **Authentication**: JWT tokens with expiration
7. **Rate Limiting**: Implemented on API endpoints

## CI/CD Pipeline

### GitHub Actions
- Ruby security scanning with Brakeman
- JavaScript dependency audit
- RSpec tests on pull requests
- ESLint and RuboCop checks
- Automated dependency updates with Dependabot

### Pre-commit Hooks (optional)
```bash
# Install overcommit
gem install overcommit
overcommit --install
overcommit --sign
```

## Monitoring and Debugging

### Logging
```ruby
# Rails
Rails.logger.info "Processing Excel file: #{file.id}"
ExcelAnalysis.logger.debug { "Detailed analysis: #{analysis.inspect}" }

# Python
logger.info(f"Analyzing VBA module: {module_name}")
```

### Performance Monitoring
- Bullet gem for N+1 query detection
- rack-mini-profiler for development
- Python service includes timing middleware
- Browser DevTools for frontend performance

### Debugging Tips
```bash
# Rails debugging
bin/rails console
binding.pry  # In code

# Vue.js debugging
# Install Vue DevTools browser extension
console.log('Component state:', this.$data)

# Python debugging
import pdb; pdb.set_trace()
```