.PHONY: help build up down restart logs shell db-create db-migrate db-seed db-reset test clean

# Default target
help:
	@echo "Excel Unified Docker Commands:"
	@echo "  make build      - Build all Docker images"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - View logs from all services"
	@echo "  make shell      - Open Rails console"
	@echo "  make bash       - Open bash shell in Rails container"
	@echo "  make db-create  - Create databases"
	@echo "  make db-migrate - Run database migrations"
	@echo "  make db-seed    - Seed the database"
	@echo "  make db-reset   - Reset database (drop, create, migrate, seed)"
	@echo "  make test       - Run tests"
	@echo "  make clean      - Remove containers and volumes"

# Build Docker images
build:
	docker-compose build

# Start services
up:
	docker-compose up -d
	@echo "Services started! Rails app: http://localhost:3000"
	@echo "Python service: http://localhost:8000"
	@echo "Mailcatcher: http://localhost:1080"

# Stop services
down:
	docker-compose down

# Restart services
restart: down up

# View logs
logs:
	docker-compose logs -f

# Rails-specific logs
rails-logs:
	docker-compose logs -f rails

# Sidekiq logs
sidekiq-logs:
	docker-compose logs -f sidekiq

# Open Rails console
shell:
	docker-compose exec rails bundle exec rails console

# Open bash shell
bash:
	docker-compose exec rails bash

# Database commands
db-create:
	docker-compose exec rails bundle exec rails db:create

db-migrate:
	docker-compose exec rails bundle exec rails db:migrate

db-seed:
	docker-compose exec rails bundle exec rails db:seed

db-reset:
	docker-compose exec rails bundle exec rails db:drop db:create db:migrate db:seed

# Run tests
test:
	docker-compose exec -e RAILS_ENV=test rails bundle exec rspec

# Run specific test file
test-file:
	@read -p "Enter test file path: " file; \
	docker-compose exec -e RAILS_ENV=test rails bundle exec rspec $$file

# Clean up
clean:
	docker-compose down -v
	docker system prune -f

# Bundle install
bundle:
	docker-compose exec rails bundle install

# NPM install
npm:
	docker-compose exec rails npm install

# Assets precompile
assets:
	docker-compose exec rails bundle exec rails assets:precompile

# Check service health
health:
	@echo "Checking service health..."
	@docker-compose ps
	@echo "\nPostgreSQL:"
	@docker-compose exec postgres pg_isready -U excel_unified || echo "PostgreSQL is not ready"
	@echo "\nRedis:"
	@docker-compose exec redis redis-cli ping || echo "Redis is not ready"
	@echo "\nRails:"
	@curl -s http://localhost:3000/api/v1/health || echo "Rails is not ready"
	@echo "\nPython:"
	@curl -s http://localhost:8000/health || echo "Python service is not ready"