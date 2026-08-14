# AGENTS.md

Inventory/point-of-sale app for a single shop, serving three surfaces:
- `webapp.py` — Flask dashboard (~3100 lines, all routes inline). Port from `PORT` env (default 5000, 8080 on Fly).
- `main.py` — Telegram reporter bot (`python-telegram-bot`), reads `TELEGRAM_BOT_TOKEN`.
- `desktop_app.py` — pywebview shell that spawns webapp.py + ngrok + bot for local desktop use (Windows only; pywebview/pywin32).

All data is SQLite. UI is English + Khmer (`km`).

## Multi-tenant architecture (read before touching DB code)

Two DB levels, defined in `system_db.py`:
- `system.db` (`SYSTEM_DB_PATH`) — shared tenant directory: `organizations`, `users_index`, `invite_keys`.
- `org_<id>.db` per organization — full app schema, one file per tenant.

Non-obvious rules:
- `db.py` resolves the active DB **at call time**: in a request context it uses `session['org_id']`; otherwise it falls back to `config.SYSTEM_DB_PATH`. Never cache a DB path at import time — org switching depends on this.
- The bot is hard-wired to Org #1: `main.py` re-points `config.SYSTEM_DB_PATH` to org 1's DB at startup.
- Schema source of truth is `system_db.bootstrap_org_db()` — new columns for org DBs (and the idempotent safety-net `ALTER`s there) must be added there too.
- `ensure_default_org()` promotes an existing `inventory.db` → `org_1.db` on first boot. On Fly, `run.sh` seeds the volume from a `seed/inventory.db` snapshot (that snapshot is NOT in the repo; it's added out-of-band at deploy time — the Dockerfile `COPY seed ./seed` will fail without it).
- Org join keys: 16-char alphanumeric, stored sha256-hashed, shown to the user once. Usernames are globally unique across orgs (`users_index.username UNIQUE`).
- Super-admin panel at `/admin/organizations`, gated by `SUPER_ADMIN_USERNAME` env. Roles: admin(100) > manager(50) > staff(10), enforced by `role_required(min_level)` in webapp.py.

Design doc: `docs/superpowers/specs/2026-08-12-multi-tenant-orgs-design.md`.

## Commands

- Tests: `python -m pytest` from repo root (tests insert `os.getcwd()` into `sys.path`, so root-relative only). DB tests monkeypatch `config.SYSTEM_DB_PATH`/`DB_PATH` to tmp paths before importing `system_db`/`webapp` — keep that pattern when adding tests.
- Run webapp locally: `python webapp.py`, then http://127.0.0.1:5000 (`/desktop-login` auto-logs-in without credentials).
- Desktop setup: `setup.bat` (venv + pip install), then `build_desktop.py` (PyInstaller). Fly deploy excludes pywebview on purpose (Dockerfile greps it out of requirements).
- No linter, typechecker, formatter config, or CI exist.

## Gotchas

- `.env` is loaded from the script/exe directory (see `config.py` `BASE_DIR`); not loaded from cwd. Env vars: `TELEGRAM_BOT_TOKEN`, `DASHBOARD_URL`, `SECRET_KEY`, `SYSTEM_DB_PATH`.
- `ADMIN_IDS = {7185846273}` is hardcoded in `config.py` — the Telegram owner bypasses the bot PIN.
- i18n lives in two places: bot strings in `translations.py` (`T`), web UI strings in `webapp.py`'s inline `DT` dict. Both are `en`/`km`.
- `main.py` and `webapp.py` run as separate processes sharing the same DBs (Fly `run.sh` starts both); don't rely on in-process globals across them.
- Commits use Conventional Commits style (`feat`, `fix`, `docs`, `deploy`, ...).
