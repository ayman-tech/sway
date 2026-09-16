.PHONY: app web api install build-web deploy logs-api logs-web

# ── local dev ────────────────────────────────────────────────────────────────

app:
	uv run apps/desktop/main.py

api:
	uv run --project apps/api uvicorn api.main:app --reload --app-dir apps/api --port 8010

web:
	npm --prefix apps/web run dev -- -p 3010

# ── production ───────────────────────────────────────────────────────────────

install:
	uv sync --project apps/api
	npm --prefix apps/web ci

build-web:
	npm --prefix apps/web run build

deploy:
	@test -n "$(WEB_ARTIFACT)" || (echo "WEB_ARTIFACT is required; production builds run in GitHub Actions" >&2; exit 2)
	flock -w 600 /tmp/sway-deploy.lock bash deploy/install-release.sh "$(WEB_ARTIFACT)"

logs-api:
	sudo journalctl -u sway-api -f

logs-web:
	sudo journalctl -u sway-web -f
