"""Обёртка над S3-совместимым хранилищем.

boto3 импортируется лениво — сервис можно запустить без него, пока S3 не нужен.
"""
from app.config import settings


def _client():
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
    )


def presign_put(key: str, content_type: str = "image/jpeg", expires: int = 3600) -> dict:
    if not settings.s3_access_key:
        raise RuntimeError("S3 не настроен (пустой S3_ACCESS_KEY в .env)")
    client = _client()
    presigned = client.generate_presigned_post(
        Bucket=settings.s3_bucket,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, 10 * 1024 * 1024],
        ],
        ExpiresIn=expires,
    )
    return {"url": presigned["url"], "fields": presigned["fields"]}


def presign_get(key: str, expires: int = 3600) -> str:
    if not settings.s3_access_key:
        return key  # заглушка — вернём ключ вместо URL
    client = _client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires,
    )
