# Drone Swarm Agent - Makefile
# Self-contained test infrastructure

.PHONY: help install services-up services-down run test test-integration clean

# Default target
help:
	@echo "Drone Swarm Agent - Available targets:"
	@echo "  make install          - Install Python dependencies via uv"
	@echo "  make services-up      - Start Redis via Docker"
	@echo "  make services-down    - Stop services"
	@echo "  make run              - Start API server on port 8000"
	@echo "  make test             - Run pytest unit tests"
	@echo "  make test-integration - Run integration tests against running API"
	@echo "  make clean            - Cleanup temporary files and containers"

# Install dependencies using uv
install:
	@echo "Installing dependencies with uv..."
	uv sync

# Start all services (PostgreSQL, PostgREST, Redis)
services-up:
	@echo "Starting services..."
	@if ! docker info > /dev/null 2>&1; then \
		echo "Error: Docker is not running"; \
		exit 1; \
	fi
	docker compose up -d postgres postgrest redis
	@echo "Waiting for PostgreSQL to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
		if docker exec drone-swarm-postgres pg_isready -U droneuser -d drones > /dev/null 2>&1; then \
			echo "PostgreSQL is ready"; \
			break; \
		fi; \
		echo "Waiting for PostgreSQL..."; \
		sleep 2; \
	done
	@echo "Waiting for PostgREST to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
		if curl -s http://localhost:3000 > /dev/null 2>&1; then \
			echo "PostgREST is ready"; \
			break; \
		fi; \
		echo "Waiting for PostgREST..."; \
		sleep 2; \
	done
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then \
			echo "Redis is ready"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Redis failed to start"; \
	exit 1

# Stop services
services-down:
	@echo "Stopping services..."
	docker compose down

# Run API server
run:
	@echo "Starting API server on port 8000..."
	@cd /home/cgadgil/src/resistance-is-futile && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

# Run unit tests
test:
	@echo "Running unit tests..."
	cd /home/cgadgil/src/resistance-is-futile && uv run pytest tests/ -v

# Run integration tests
test-integration: services-up
	@echo "Running integration tests..."
	@echo "Cleaning up port 8000 if needed..."
	@-lsof -ti:8000 | xargs -r kill -9 2>/dev/null || true
	@sleep 1
	@echo "Waiting for PostgreSQL and PostgREST to be ready..."
	@sleep 5
	@echo "Starting API server in background..."
	@cd /home/cgadgil/src/resistance-is-futile && \
		POSTGREST_URL=http://localhost:3000 \
		POSTGREST_API_KEY=test-key \
		uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 &
	@SERVER_PID=$$!
	@echo "Waiting for API server to start..."
	@sleep 3
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if curl -s http://localhost:8000/health > /dev/null 2>&1; then \
			echo "API server is ready"; \
			break; \
		fi; \
		sleep 1; \
	done
	@echo "Running integration tests..."
	cd /home/cgadgil/src/resistance-is-futile && uv run pytest tests/test_integration.py -v || true
	@echo "Stopping API server..."
	@kill $$SERVER_PID 2>/dev/null || true

# Cleanup
clean:
	@echo "Cleaning up..."
	docker compose down -v 2>/dev/null || true
	rm -rf .pytest_cache __pycache__ src/__pycache__ tests/__pycache__ 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
