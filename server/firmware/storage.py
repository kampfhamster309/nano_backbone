from storages.backends.s3boto3 import S3Boto3Storage


class FirmwareS3Storage(S3Boto3Storage):
    """S3-compatible storage for firmware release files."""
    pass
