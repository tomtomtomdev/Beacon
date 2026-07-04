.PHONY: verify verify-backend verify-frontend test setup

verify: verify-backend verify-frontend
verify-backend:  ; cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
verify-frontend: ; cd frontend && npx eslint . && npx tsc --noEmit && npx vitest run
test:            ; cd backend && uv run pytest ; cd ../frontend && npx vitest run
setup:           ; cd backend && uv sync ; cd ../frontend && npm install
