from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_secret: str = "dev-secret-change-me"
    cors_origins: str = "*"

    database_url: str = "sqlite:///./proshot.db"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint: str = ""
    s3_region: str = "ru-central1"
    s3_bucket: str = "proshot-uploads"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # provod.ai
    provod_api_url: str = "https://api.provod.ai/v1"
    provod_api_key: str = ""
    provod_model: str = "openai/gpt-image-2"
    provod_size: str = "1024x1024"
    provod_quality: str = "low"

    # DashScope (Alibaba Cloud Model Studio)
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/api/v1"
    dashscope_model: str = "qwen-image-edit-plus"

    # Ветка «доверять клиенту» в google_play.py читалась через getattr, а поля не было,
    # то есть она никогда не включалась. Поле заведено явно; значение по умолчанию
    # сохраняет ровно то же поведение — без ключа покупка не проходит.
    allow_unverified_purchases: bool = False

    google_service_account_json: str = ""
    google_package_name: str = "ai.proshot.app"

    # --- Apple / StoreKit 2 ---
    # bundle_id совпадает с applicationId Android-версии: пространства имён
    # Apple и Google независимы, конфликта нет.
    apple_bundle_id: str = "ai.proshot.app"
    # Числовой идентификатор приложения из App Store Connect. Нужен библиотеке
    # проверки; пока приложение не заведено — 0, тогда передаём None.
    apple_app_apple_id: int = 0
    # Папка с корневыми сертификатами Apple (.cer). Без них подпись не проверить.
    apple_root_ca_dir: str = ""
    # Ключ для App Store Server API: файл .p8 плюс два идентификатора.
    apple_key_id: str = ""
    apple_issuer_id: str = ""
    apple_private_key_path: str = ""
    # Онлайн-проверка отзыва сертификатов при разборе подписи. Дороже и требует
    # сети на каждую покупку, поэтому по умолчанию выключена.
    apple_online_checks: bool = False


settings = Settings()
