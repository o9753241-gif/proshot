"""Превью сцен: JPEG с on-demand ресайзом и кэшем на диск.

По образцу star-app:
  GET /api/v1/thumbs/{scene_key}?w=600
  - если w=0 или w>=оригинала -> отдаём оригинал
  - иначе -> ресайзим через PIL, кэшируем в thumbs/w{N}/, отдаём JPEG q=85
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter()

MEDIA_DIR = Path("./media/thumbs")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/{scene_key}")
def get_thumb(scene_key: str, w: int = Query(0, ge=0, le=2048)):
    # защита от path-traversal
    safe = Path(scene_key).name + ".jpg"
    original = MEDIA_DIR / safe
    if not original.exists():
        raise HTTPException(404, f"No thumbnail for '{scene_key}'")

    # Без ресайза — отдаём оригинал (FastAPI использует sendfile, очень быстро)
    if w == 0 or w >= 1024:
        return FileResponse(
            original,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=2592000"},  # 30 дней
        )

    # Кэшируем ресайзы на диск
    cache_dir = MEDIA_DIR / f"w{w}"
    cache_dir.mkdir(exist_ok=True)
    cached = cache_dir / safe
    if not cached.exists():
        from PIL import Image
        with Image.open(original) as img:
            img = img.convert("RGB")
            img.thumbnail((w, w * 4), Image.LANCZOS)
            img.save(cached, format="JPEG", quality=85, optimize=True)
    return FileResponse(
        cached,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=2592000"},
    )
