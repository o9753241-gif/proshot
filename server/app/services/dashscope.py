"""Клиент DashScope. Синхронный вызов qwen-image-edit-plus по HTTP-ссылке на входное фото."""
import httpx
import random
from app.config import settings


class DashScopeError(RuntimeError):
    pass


def edit_image_by_url(
    reference_image_url: str,
    prompt: str,
    model: str | None = None,
    size: str = "2K",
    timeout_s: int = 180,
) -> bytes:
    """Синхронный вызов. reference_image_url — публичная HTTP(S) ссылка на фото."""
    model = model or getattr(settings, "dashscope_model", "qwen-image-edit-plus") or "qwen-image-edit-plus"
    key = getattr(settings, "dashscope_api_key", "") or ""
    if not key:
        raise DashScopeError("DASHSCOPE_API_KEY не задан")
    base = (getattr(settings, "dashscope_base_url", "") or "https://dashscope-intl.aliyuncs.com/api/v1").rstrip("/")

    r = httpx.post(
        f"{base}/services/aigc/multimodal-generation/generation",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": [
                        {"image": reference_image_url},
                        {"text": prompt},
                    ],
                }]
            },
            "parameters": {"size": size, "n": 1, "watermark": False, "seed": random.randint(0, 2**31 - 1)},
        },
        timeout=timeout_s,
    )

    if r.status_code != 200:
        raise DashScopeError(f"DashScope HTTP {r.status_code}: {r.text[:800]}")
    payload = r.json()

    try:
        content = payload["output"]["choices"][0]["message"]["content"]
        img_item = next((c for c in content if isinstance(c, dict) and "image" in c), None)
        if not img_item:
            raise DashScopeError(f"no image in response: {payload}")
        img_url = img_item["image"]
    except (KeyError, IndexError, TypeError) as e:
        raise DashScopeError(f"unexpected response: {payload}") from e

    img_r = httpx.get(img_url, timeout=60.0)
    if img_r.status_code != 200:
        raise DashScopeError(f"can't download result: HTTP {img_r.status_code}")
    return img_r.content
