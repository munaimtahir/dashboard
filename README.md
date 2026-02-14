# Dashboard v1

Clean-slate, manifest-driven server dashboard.

## Start/stop

```bash
cd /home/munaim/srv/dashboard
docker compose up -d --build
# stop
docker compose down
```

## Admin login

Edit `/home/munaim/srv/dashboard/.env`:

- `ADMIN_PASSWORD`: single shared admin password
- `JWT_SECRET`: token signing secret
- `REQUEST_TIMEOUT_SECONDS`: HTTP check timeout (default `3` seconds)

Restart after changes:

```bash
docker compose up -d --build
```

## Manifest

Edit `/home/munaim/srv/dashboard/manifest.yml`.

Each app defines a safe allowlist of containers. The backend will ONLY start/stop/restart containers listed under that app.

The `/api/discover` endpoint helps you find container names.

## Down reason

The backend computes `reason` and `recommendation`:

- If any listed container is missing or not running: `Container stopped/missing (exit <code>)`
- Else if backend health URL fails: `Backend health failing`
- Else if frontend URL fails: `Frontend unreachable`
- Else: `OK`

## Safety scope (v1)

- No Docker build/pull/prune endpoints.
- Backend is not published to the host; only the frontend is exposed on `127.0.0.1:8013`.
- All container control operations are allowlist-only (from `manifest.yml`).
- Action endpoints are rate-limited (max 3 actions per app per 5 minutes) and audited to SQLite.
