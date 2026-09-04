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
    sku: str
    purchase_token: str
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


class StartTrainingRequest(BaseModel):
    purchase_id: int
    photo_keys: list[str]


class TrainingOut(BaseModel):
    id: int
    status: str
    provod_model_id: str | None


class StyleOut(BaseModel):
    key: str
    title: str
    preview_url: str
    tier: int


class StartGenerationRequest(BaseModel):
    training_id: int
    style_key: str


class GenerationOut(BaseModel):
    id: int
    status: str
    result_urls: list[str] = []
