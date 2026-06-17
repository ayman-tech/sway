.PHONY: app web api mcp install build-web deploy logs-api logs-web

# ── local dev ────────────────────────────────────────────────────────────────

app:
	uv run apps/desktop/main.py

api:
	uv run --project apps/api uvicorn api.main:app --reload --app-dir apps/api --port 8010

web:
	npm --prefix apps/web run dev -- -p 3010

mcp:
	uv run --project apps/mcp sway-mcp

# ── production ───────────────────────────────────────────────────────────────

install:
	uv sync --project apps/api
	npm --prefix apps/web ci

build-web:
	npm --prefix apps/web run build

deploy:
	git checkout main -f
	git pull origin main
	uv sync --project apps/api
	npm --prefix apps/web ci
	npm --prefix apps/web run build
	sudo systemctl restart sway-api sway-web

logs-api:
	sudo journalctl -u sway-api -f

logs-web:
	sudo journalctl -u sway-web -f
