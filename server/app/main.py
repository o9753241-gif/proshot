import logging
import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import settings
from app.db import Base, engine
from app.routers import auth, packages, billing, uploads, styles, generation, thumbs, device
from app.services import app_attest

# Без этого логгеры приложения молчат ниже WARNING: uvicorn настраивает только свои.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

Base.metadata.create_all(bind=engine)


def _migrate() -> None:
    """create_all не добавляет колонки в существующие таблицы — добавляем сами.
    Повторный запуск ничего не меняет."""
    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.begin() as con:
        if "token_issued" not in cols:
            con.execute(text("ALTER TABLE users ADD COLUMN token_issued BOOLEAN NOT NULL DEFAULT 0"))
        if "attested" not in cols:
            con.execute(text("ALTER TABLE users ADD COLUMN attested BOOLEAN NOT NULL DEFAULT 0"))


_migrate()


def _check_config() -> None:
    """Одна строка в журнал при старте: всё ли нужное для денег настроено.
    Латиницей — терминал владельца съедает кириллицу."""
    problems = []
    if not settings.apple_app_apple_id:
        problems.append("APPLE_APP_APPLE_ID=0 (purchases fail)")
    roots = settings.apple_root_ca_dir
    if not roots or not os.path.isdir(roots) or not any(
            n.endswith(".cer") for n in os.listdir(roots)):
        problems.append("APPLE_ROOT_CA_DIR empty (purchases fail)")
    if not os.environ.get("PUBLIC_BASE_URL"):
        problems.append("PUBLIC_BASE_URL not set")
    if not settings.dashscope_api_key:
        problems.append("DASHSCOPE_API_KEY empty (generation fails)")
    if app_attest.mode() == "enforce" and not app_attest.available():
        problems.append("ATTEST_MODE=enforce but attestation not configured: everyone gets 403")
    if problems:
        print("[CONFIG] PROBLEMS: " + "; ".join(problems), flush=True)
    else:
        print(f"[CONFIG] OK attest={app_attest.mode()} "
              f"attest_ready={app_attest.available()}", flush=True)


_check_config()

app = FastAPI(title="ProShot API (iOS)", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,       prefix="/api/v1/auth",       tags=["auth"])
app.include_router(packages.router,   prefix="/api/v1/packages",   tags=["packages"])
app.include_router(billing.router,    prefix="/api/v1/billing",    tags=["billing"])
app.include_router(uploads.router,    prefix="/api/v1/uploads",    tags=["uploads"])
app.include_router(styles.router,     prefix="/api/v1/styles",     tags=["styles"])
app.include_router(generation.router, prefix="/api/v1/generation", tags=["generation"])
app.include_router(thumbs.router,     prefix="/api/v1/thumbs",     tags=["thumbs"])
app.include_router(device.router,     prefix="/api/v1/device",     tags=["device"])


@app.get("/health")
def health(response: Response):
    """Живость для внешнего мониторинга.

    На боевом сервере было два обработчика с этим путём: информационный и
    добавленный позже с проверкой базы. FastAPI отдаёт первый совпавший, так что
    проверка базы никогда не выполнялась и мониторинг видел «ок» при мёртвой базе.
    Здесь обработчик один.

    База берётся из настроек, а не из зашитого пути: у iOS-инстанса своя.
    """
    db_ok = True
    try:
        with engine.connect() as con:
            from sqlalchemy import text
            con.execute(text("select 1"))
    except Exception:
        db_ok = False

    if not db_ok:
        response.status_code = 503
        return {"status": "db_error"}

    return {
        "status": "ok",
        "env": settings.app_env,
        "platform": "ios",
    }
