"""Object storage: S3-compatible (boto3 / MinIO) or Alibaba OSS (oss2)."""
from __future__ import annotations

from pathlib import Path

import settings

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore
    Config = None  # type: ignore
    ClientError = Exception  # type: ignore

try:
    import oss2
except ImportError:  # pragma: no cover
    oss2 = None  # type: ignore


def build_object_key(user_id: str, recording_id: str) -> str:
    """Returns the object key for a recording."""
    return f"VLM_FILE_STORAGE/tenant_{user_id}/{recording_id}.wav"


def _s3_client():
    if boto3 is None or Config is None:
        raise RuntimeError("boto3 is required for S3-compatible storage")
    addressing = (settings.S3_ADDRESSING_STYLE or "path").strip() or "path"
    cfg = Config(
        signature_version="s3v4",
        s3={"addressing_style": addressing},
    )
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
        use_ssl=settings.S3_USE_SSL,
        config=cfg,
    )


def _ensure_s3_bucket() -> None:
    client = _s3_client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET)
    except ClientError:
        try:
            client.create_bucket(Bucket=settings.S3_BUCKET)
        except ClientError:
            pass


def _oss_bucket():
    if oss2 is None:
        raise RuntimeError("oss2 is required for Alibaba OSS storage")
    auth = oss2.Auth(settings.OSS_ACCESS_KEY_ID, settings.OSS_ACCESS_KEY_SECRET)
    return oss2.Bucket(
        auth,
        settings.OSS_ENDPOINT,
        settings.OSS_BUCKET_NAME,
        connect_timeout=30,
    )


def upload_wav_file(local_path: str | Path, object_key: str) -> str:
    """Upload WAV; returns object_key."""
    if not settings.object_storage_configured():
        raise RuntimeError("Object storage not configured")
    path = Path(local_path)
    if settings.s3_configured():
        _ensure_s3_bucket()
        client = _s3_client()
        client.upload_file(
            str(path),
            settings.S3_BUCKET,
            object_key,
            ExtraArgs={"ContentType": "audio/wav"},
        )
        return object_key
    if settings.oss_configured():
        bucket = _oss_bucket()
        bucket.put_object_from_file(
            object_key,
            str(path),
            headers={"Content-Type": "audio/wav"},
        )
        return object_key
    raise RuntimeError("No storage backend configured")


def public_url(object_key: str) -> str:
    """Public-facing URL (best-effort for MinIO without S3_PUBLIC_BASE_URL)."""
    if settings.s3_configured():
        if settings.S3_PUBLIC_BASE_URL:
            return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{object_key}"
        base = settings.S3_ENDPOINT.rstrip("/")
        return f"{base}/{settings.S3_BUCKET}/{object_key}"
    if settings.oss_configured():
        return f"{settings.OSS_PUBLIC_ENDPOINT.rstrip('/')}/{object_key}"
    raise RuntimeError("Object storage not configured")


def check_exists(object_key: str) -> bool:
    if settings.s3_configured():
        client = _s3_client()
        try:
            client.head_object(Bucket=settings.S3_BUCKET, Key=object_key)
            return True
        except ClientError:
            return False
    if settings.oss_configured():
        return _oss_bucket().object_exists(object_key)
    raise RuntimeError("Object storage not configured")


def delete_file(object_key: str) -> None:
    if settings.s3_configured():
        _s3_client().delete_object(Bucket=settings.S3_BUCKET, Key=object_key)
        return
    if settings.oss_configured():
        _oss_bucket().delete_object(object_key)
        return
    raise RuntimeError("Object storage not configured")


def generate_signed_url(object_key: str, expires: int = 86400) -> str:
    """Return a pre-signed GET URL valid for `expires` seconds (default 24 h)."""
    if settings.s3_configured():
        if boto3 is None:
            raise RuntimeError("boto3 required for signed URLs")
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": object_key},
            ExpiresIn=expires,
        )
    if settings.oss_configured():
        if oss2 is None:
            raise RuntimeError("oss2 required for signed URLs")
        return _oss_bucket().sign_url("GET", object_key, expires)
    raise RuntimeError("Object storage not configured")
