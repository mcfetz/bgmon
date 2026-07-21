# Deploy — bgmon

## Ablauf (nach jedem produktiven Commit)

```bash
# 1. Lokale Checks
cd backend && source .venv/bin/activate
ruff check bgmon_api/
python -m compileall -q bgmon_api/
cd ../frontend && npm run build

# 2. Pushen
cd ..
git push origin main          # → git.familie-heise.de (Primär)
git push github main          # → GitHub (CI + Image-Build)

# 3. GitHub CI abwarten
# → https://github.com/mcfetz/bgmon/actions
# Alle Jobs (backend, frontend, docker-build) müssen grün sein.

# 4. Redeploy im Docker Swarm via Portainer Webhooks
# Beide Webhooks sind idempotent — immer beide aufrufen.
curl -X POST "https://portainer.familie-heise.de/api/webhooks/39c4ba3d-a9c8-45e1-8c88-3fb1e4383747"   # bgmon-app
curl -X POST "https://portainer.familie-heise.de/api/webhooks/2f05730b-c4ad-4b44-a0c0-e581e2a1cea1"   # bgmon-scheduler

# 5. Benachrichtigung senden (ntfy)
ntfy_ntfy_me title="bgmon deploy" message="Deploy erfolgreich: commit $SHA" priority="low"
```

## Bemerkungen

- **Docker-Image** wird von GitHub CI gebaut und in `ghcr.io` gepusht (via `docker/build-push-action`).
- **Portainer** pullt das neue Image und rollt den Stack `bgmon` neu aus.
- **Kein manuelles `docker build`** nötig — das macht die CI.
- Bei Fehlern: in der CI nachschauen, fixen, erneut pushen.