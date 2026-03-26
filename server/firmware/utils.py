import hashlib

import boto3
from django.conf import settings


def generate_presigned_url(object_key: str, expiry_seconds: int = 300) -> str:
    # Use a separate public endpoint for presigned URLs if configured — the storage
    # endpoint may be an internal Docker hostname unreachable by external clients.
    endpoint = getattr(settings, "AWS_S3_PRESIGNED_ENDPOINT_URL", None) or settings.AWS_S3_ENDPOINT_URL
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
    )
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": object_key},
        ExpiresIn=expiry_seconds,
    )


def compute_sha256(file_obj) -> str:
    file_obj.seek(0)
    h = hashlib.sha256()
    for chunk in iter(lambda: file_obj.read(8192), b""):
        h.update(chunk)
    file_obj.seek(0)
    return h.hexdigest()
