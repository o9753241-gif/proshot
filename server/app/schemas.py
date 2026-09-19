from pydantic import BaseModel


class AuthRequest(BaseModel):
    device_id: str


class AuthResponse(BaseModel):
    token: str
    user_id: int


class PackageOut(BaseModel):
    sku: str
    title: str
    scenes_pool: int
    max_scenes: int
    total_photos: int
    price_rub: int          # исходная цена в рублях (аналитика)
    price_display: str      # готовая строка для UI: "990 ₽" | "$9.99" | "€9,99"
    currency: str           # RUB / USD / EUR


class VerifyPurchaseRequest(BaseModel):
    """Запрос на начисление пакета после оплаты.

    Провайдер выбирается полем provider, а не догадками по содержимому:
    у Apple приходит подписанный документ в signed_transaction, у Google —
    токен в purchase_token. Значение по умолчанию — app_store, потому что
    этот сервер обслуживает iOS-версию.
    """
    sku: str
    provider: str = "app_store"
    signed_transaction: str | None = None
    purchase_token: str | None = None
    scenes_selected: list[str] = []


class PurchaseOut(BaseModel):
    id: int
    sku: str
    status: str
    scenes_selected: list[str]
    photos_remaining: int


class PresignRequest(BaseModel):
    purchase_id: int
    count: int


class PresignedUpload(BaseModel):
    key: str
    url: str
    fields: dict


class PresignResponse(BaseModel):
    uploads: list[PresignedUpload]


class StyleOut(BaseModel):
    key: str
    title: str
    preview_url: str
    tier: int


class IndustryOut(BaseModel):
    """Отраслевая подборка сцен: чем человек занимается, то ему и показываем."""
    key: str
    title: str
    scene_count: int
    preview_url: str
