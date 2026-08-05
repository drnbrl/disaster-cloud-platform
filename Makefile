SHELL := /bin/bash
.PHONY: install backend-install frontend-install test backend-test frontend-test backend-build backend-deploy frontend-dev clean

install: backend-install frontend-install
backend-install:
	cd backend && python3.12 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip && pip install -r requirements-dev.txt
frontend-install:
	cd frontend && npm install
test: backend-test frontend-test
backend-test:
	cd backend && source .venv/bin/activate && pytest
frontend-test:
	cd frontend && npm run build
backend-build:
	cd backend && sam validate && sam build --use-container
backend-deploy:
	cd backend && sam deploy --guided
frontend-dev:
	cd frontend && npm run dev
clean:
	rm -rf backend/.aws-sam frontend/dist frontend/node_modules backend/.pytest_cache
	find backend -type d -name __pycache__ -prune -exec rm -rf {} +
