from __future__ import annotations

import base64
import logging
import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api import listing_routes, misc_routes, personal_routes, search_routes
from app.config import BACKEND_DIR, REPO_DIR, get_settings
from app.db import migrate, session_scope
from app.models import Profile
from app.state import STATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("autozoeker")

DEFAULT_PROFILES = ["Pim", "Eline"]


def ensure_profiles() -> None:
    with session_scope() as session:
        existing = {p.name for p in session.scalars(select(Profile))}
        for name in DEFAULT_PROFILES:
            if name not in existing:
                session.add(Profile(name=name))


def warm_up() -> None:
    """Seed demo data and train the valuation model without blocking startup."""
    from app.analysis import refresh
    from app.demo.seed import seed_demo
    from app.valuation.model import get_model_instance

    settings = get_settings()
    try:
        with session_scope() as session:
            if settings.demo_mode:
                STATE["message"] = "Demo-data laden…"
                seed_demo(session)
        if get_model_instance() is None:
            STATE["message"] = "Waarderingsmodel trainen…"
            with session_scope() as session:
                refresh(session, retrain=True)
        STATE.update(ready=True, message="")
    except Exception as exc:  # keep the API up; status page shows the problem
        log.exception("warm-up failed")
        STATE.update(ready=True, message=f"Opstarten deels mislukt: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import scheduler

    migrate()
    ensure_profiles()
    threading.Thread(target=warm_up, daemon=True).start()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="Autozoeker", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    settings = get_settings()
    if settings.basic_auth_user and settings.basic_auth_password:
        header = request.headers.get("authorization", "")
        ok = False
        if header.lower().startswith("basic "):
            try:
                user, _, pw = base64.b64decode(header[6:]).decode().partition(":")
                ok = secrets.compare_digest(user, settings.basic_auth_user) and secrets.compare_digest(
                    pw, settings.basic_auth_password)
            except Exception:
                ok = False
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Autozoeker"'})
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"ok": True, "ready": STATE["ready"], "message": STATE["message"]}


app.include_router(search_routes.router)
app.include_router(listing_routes.router)
app.include_router(personal_routes.router)
app.include_router(misc_routes.router)


def _static_dir() -> Path | None:
    for candidate in (BACKEND_DIR / "app" / "static", REPO_DIR / "frontend" / "dist"):
        if (candidate / "index.html").exists():
            return candidate
    return None


_static = _static_dir()
if _static is not None:
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        target = (_static / full_path).resolve()
        if full_path and target.is_file() and target.is_relative_to(_static.resolve()):
            return FileResponse(target)
        return FileResponse(_static / "index.html")
