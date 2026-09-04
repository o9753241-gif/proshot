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

# ── Apple отказала в возврате ──
from app.routers.billing import apply_refund_reversed, build_consumption, _photos_used  # noqa: E402
from app.models import GenerationEvent  # noqa: E402

back = apply_refund_reversed(db, tx)
check("отмена возврата восстанавливает остаток",
      back is not None and back.status == "paid" and back.photos_remaining == 20)

# Три снимка уже получены — остаток после отмены возврата должен это учесть.
for i in range(3):
    db.add(GenerationEvent(user_id=user.id, purchase_id=back.id, scene_key="business_light"))
db.commit()
apply_refund(db, tx)
back2 = apply_refund_reversed(db, tx)
check("восстановлен остаток за вычетом израсходованного",
      back2.photos_remaining == 17, f"(получено {back2.photos_remaining})")

# ── Ответ на CONSUMPTION_REQUEST ──
from app.config import Settings as S  # noqa: E402
import app.routers.billing as B  # noqa: E402

B.settings = S(apple_consumption_consented=False)
cr = build_consumption(db, tx)
check("без согласия отправляем только customerConsented=false",
      cr is not None and cr.customerConsented is False and cr.consumptionStatus is None)

B.settings = S(apple_consumption_consented=True)
cr = build_consumption(db, tx)
from appstoreserverlibrary.models.ConsumptionStatus import ConsumptionStatus  # noqa: E402
from appstoreserverlibrary.models.DeliveryStatus import DeliveryStatus  # noqa: E402
from appstoreserverlibrary.models.RefundPreference import RefundPreference  # noqa: E402
check("частичный расход виден как PARTIALLY_CONSUMED",
      cr.consumptionStatus == ConsumptionStatus.PARTIALLY_CONSUMED)
check("доставка отмечена как успешная",
      cr.deliveryStatus == DeliveryStatus.DELIVERED_AND_WORKING_PROPERLY)
check("при частичном расходе позиции по возврату нет",
      cr.refundPreference == RefundPreference.NO_PREFERENCE)
check("appAccountToken — это device_id", cr.appAccountToken == user.device_id)

# Дорасходуем пакет до конца и проверим позицию по возврату.
for i in range(17):
    db.add(GenerationEvent(user_id=user.id, purchase_id=back2.id, scene_key="business_light"))
db.commit()
cr = build_consumption(db, tx)
check("израсходованный пакет — FULLY_CONSUMED",
      cr.consumptionStatus == ConsumptionStatus.FULLY_CONSUMED)
check("по израсходованному пакету возражаем против возврата",
      cr.refundPreference == RefundPreference.PREFER_DECLINE)

check("CONSUMPTION_REQUEST по неизвестной транзакции — None",
      build_consumption(db, "НЕТ-ТАКОЙ") is None)

B.settings = S()
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
