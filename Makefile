.PHONY: dev build test lint migrate help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start development environment with docker compose
	docker compose up --build

build: ## Build production Docker image
	docker build -t bgmon:latest .

test: ## Run all tests (backend + frontend)
	$(MAKE) test-backend
	$(MAKE) test-frontend

test-backend: ## Run backend tests
	cd backend && python -m pytest -q

test-frontend: ## Run frontend tests
	cd frontend && npm run test

lint: ## Run all linters
	$(MAKE) lint-backend
	$(MAKE) lint-frontend

lint-backend: ## Lint backend with ruff and type-check with ty
	cd backend && ruff check .
	cd backend && ty check bgmon_api

lint-frontend: ## Lint frontend
	cd frontend && npm run lint
	cd frontend && npx tsc --noEmit

migrate: ## Run database migrations
	cd backend && flask --app bgmon_api.app db upgrade

migrate-revision: ## Create a new migration revision (message=M)
	cd backend && flask --app bgmon_api.app db revision --autogenerate -m "$(message)"

swarm-deploy: ## Deploy stack to Docker Swarm
	docker stack deploy -c docker-compose.swarm.yml bgmon

swarm-remove: ## Remove stack from Docker Swarm
	docker stack rm bgmon

swarm-logs: ## Show logs from Swarm services
	docker service logs -f bgmon_app

swarm-ps: ## List Swarm services
	docker stack ps bgmon

swarm-build-push: ## Build and push image for Swarm (registry=...)
	docker build -t $(registry)/bgmon:latest .
	docker push $(registry)/bgmon:latest
