"""Проверка развилки покупок без обращения к Apple.

Запуск из папки server:
    PYTHONPATH=. ALLOW_UNVERIFIED_PURCHASES=true python tests/test_billing_flow.py

Флаг ALLOW_UNVERIFIED_PURCHASES включает режим «доверять клиенту» — он существует
только для таких прогонов и локальной разработки. На сервере он должен быть false,
иначе пакет фото получит любой, кто отправит запрос.
"""
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///./flow_test.db")
os.environ.setdefault("ALLOW_UNVERIFIED_PURCHASES", "true")
os.environ.setdefault("APPLE_BUNDLE_ID", "ai.proshot.app")

if os.path.exists("flow_test.db"):
    os.remove("flow_test.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

c = TestClient(app)
H = {"X-Device-Id": "TEST-DEVICE-1", "Accept-Language": "en-US"}
BODY = {
    "sku": "pack_basic",
    "provider": "app_store",
    "signed_transaction": "FAKE.JWS.AAA",
    "scenes_selected": ["business_light", "corporate_navy"],
}

fails = []


def check(name, cond, extra=""):
    print(("  ок    " if cond else "  ПЛОХО ") + name + (f"  {extra}" if extra else ""))
    if not cond:
        fails.append(name)


check("регистрация устройства",
      c.post("/api/v1/auth/device", json={"device_id": "TEST-DEVICE-1"}).status_code == 200)

pk = c.get("/api/v1/packages", headers=H).json()
check("пакеты отдаются в валюте языка", [p["price_display"] for p in pk] == ["$9.99", "$19.99", "$29.99"])

r1 = c.post("/api/v1/billing/verify", json=BODY, headers=H)
check("покупка начисляет фото пакета", r1.status_code == 200 and r1.json()["photos_remaining"] == 20)

r2 = c.post("/api/v1/billing/verify", json=BODY, headers=H)
check("повтор транзакции не начисляет второй раз",
      r2.status_code == 200 and r2.json()["id"] == r1.json()["id"])

bad = {**BODY, "scenes_selected": ["a", "b", "c", "d"]}
check("сцен больше max_scenes — отказ",
      c.post("/api/v1/billing/verify", json=bad, headers=H).status_code == 400)

miss = {"sku": "pack_basic", "provider": "app_store", "scenes_selected": ["business_light"]}
check("без signed_transaction — отказ",
      c.post("/api/v1/billing/verify", json=miss, headers=H).status_code == 400)

check("неизвестный провайдер — отказ",
      c.post("/api/v1/billing/verify", json={**BODY, "provider": "paypal"}, headers=H).status_code == 400)

check("уведомление с неверной подписью — отказ",
      c.post("/api/v1/billing/apple/notifications", json={"signedPayload": "FAKE"}).status_code == 400)

# ── Возврат денег ──
from app.db import SessionLocal  # noqa: E402
from app.models import Purchase  # noqa: E402
from app.routers.billing import apply_refund  # noqa: E402

db = SessionLocal()
tx = db.query(Purchase).filter(Purchase.id == r1.json()["id"]).first().provider_token
refunded = apply_refund(db, tx)
check("возврат обнуляет остаток фото",
      refunded is not None and refunded.photos_remaining == 0 and refunded.status == "refunded")

# Генерация после возврата не должна находить активную покупку.
from app.routers.generation import _active_purchase  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from app.models import User  # noqa: E402

user = db.query(User).filter(User.device_id == "TEST-DEVICE-1").first()
try:
    _active_purchase(db, user)
    stopped = False
except HTTPException as e:
    stopped = e.status_code == 402
check("после возврата генерация останавливается", stopped)

check("возврат по неизвестной транзакции не падает", apply_refund(db, "НЕТ-ТАКОЙ") is None)
db.close()

del os.environ["ALLOW_UNVERIFIED_PURCHASES"]
from app.config import Settings  # noqa: E402
from app.services import app_store  # noqa: E402
app_store.settings = Settings(allow_unverified_purchases=False)
check("без сертификатов и без флага покупка не проходит",
      app_store.verify_purchase("pack_basic", "FAKE.JWS.BBB").ok is False)

print()
if fails:
    print("НЕ ПРОШЛО:", ", ".join(fails))
    sys.exit(1)
print("Все проверки прошли.")
