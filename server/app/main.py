from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, engine
from app.routers import auth, packages, billing, uploads, training, styles, generation, thumbs

Base.metadata.create_all(bind=engine)

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
app.include_router(training.router,   prefix="/api/v1/training",   tags=["training"])
app.include_router(styles.router,     prefix="/api/v1/styles",     tags=["styles"])
app.include_router(generation.router, prefix="/api/v1/generation", tags=["generation"])
app.include_router(thumbs.router,     prefix="/api/v1/thumbs",     tags=["thumbs"])


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
