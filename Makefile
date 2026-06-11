.PHONY: app web api mcp

app:
	uv run apps/desktop/main.py

api:
	uv run --project apps/api uvicorn api.main:app --reload --app-dir apps/api

web:
	npm --prefix apps/web run dev

mcp:
	uv run --project apps/mcp sway-mcp
