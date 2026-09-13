.PHONY: verify verify-backend verify-frontend test setup run

# nvm lives in an interactive profile, so npm/npx are absent from a make recipe. Every
# node-touching target sources this first — a missing npm fails the target loudly (127)
# instead of letting the frontend half of the gate skip while the backend prints green.
WITH_NODE := . scripts/node-path.sh

verify: verify-backend verify-frontend
verify-backend:  ; cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
verify-frontend: ; $(WITH_NODE) && cd frontend && npx eslint . && npx tsc --noEmit && npx vitest run
test:            ; $(WITH_NODE) && cd backend && uv run pytest ; cd ../frontend && npx vitest run
setup:           ; $(WITH_NODE) && cd backend && uv sync ; cd ../frontend && npm install
run:             ; ./run.sh
