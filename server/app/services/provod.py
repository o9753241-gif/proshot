"""Клиент provod.ai (OpenAI-совместимый endpoint /images/edits).

Формат вызова — точно как в проверенном star-app бэке на этом же сервере.
Модель, размер и quality берутся из .env.

ENV (см. .env):
  PROVOD_API_KEY   — ключ
  PROVOD_BASE_URL  — по умолчанию https://api.provod.ai/v1
  PROVOD_MODEL     — например openai/gpt-image-2
  PROVOD_SIZE      — по умолчанию 1024x1024
  PROVOD_QUALITY   — low | medium | high | auto
"""
import base64
import uuid
from pathlib import Path

import httpx

from app.config import settings


class ProvodError(RuntimeError):
    pass


def generate_headshot(
    reference_image_path: Path,
    prompt: str,
    size: str | None = None,
) -> bytes:
    """
    Генерируем один хедшот. На вход — фото пользователя и полный промт.
    Возвращаем сырые байты картинки (JPEG/PNG).
    """
    if not settings.provod_api_key:
        raise ProvodError("PROVOD_API_KEY не задан в .env на сервере")

    url = f"{settings.provod_api_url.rstrip('/')}/images/edits"
    headers = {"Authorization": f"Bearer {settings.provod_api_key}"}

    with open(reference_image_path, "rb") as f:
        files = {"image": ("input.jpg", f, "image/jpeg")}
        data = {
            "model": settings.provod_model or "openai/gpt-image-2",
            "prompt": prompt,
            "n": "1",
            "size": size or (settings.provod_size or "1024x1024"),
            "quality": settings.provod_quality or "low",
        }
        try:
            r = httpx.post(url, headers=headers, files=files, data=data, timeout=180.0)
        except httpx.HTTPError as e:
            raise ProvodError(f"provod.ai connect error: {e}") from e

    if r.status_code != 200:
        raise ProvodError(f"provod.ai HTTP {r.status_code}: {r.text[:800]}")

    try:
        payload = r.json()
        item = payload["data"][0]
    except Exception as e:
        raise ProvodError(f"provod.ai bad response: {r.text[:500]}") from e

    if "b64_json" in item:
        return base64.b64decode(item["b64_json"])
    if "url" in item:
        img = httpx.get(item["url"], timeout=60.0)
        if img.status_code != 200:
            raise ProvodError(f"can't download result: HTTP {img.status_code}")
        return img.content
    raise ProvodError(f"provod.ai: no b64_json/url in response: {item}")


# --- Совместимость со старыми стабами (не удаляем, вдруг где вызываются) ---

def start_training(user_id: int, photo_keys: list[str]) -> str:
    if not photo_keys:
        return f"stub_model_{uuid.uuid4().hex[:12]}"
    return f"user_{user_id}_ref_{photo_keys[0]}"


def start_generation(model_id: str, style_key: str) -> str:
    return f"stub_job_{uuid.uuid4().hex[:12]}"


def get_generation_status(job_id: str) -> dict:
    return {"status": "running", "result_keys": []}
