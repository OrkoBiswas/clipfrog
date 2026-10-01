import boto3
from botocore.config import Config

from clipforge_api.config import settings


def s3(public: bool = False):  # type: ignore[no-untyped-def]
    cfg = settings()
    return boto3.client(
        "s3",
        endpoint_url=cfg.s3_public_endpoint if public else cfg.s3_endpoint,
        region_name=cfg.s3_region,
        aws_access_key_id=cfg.s3_access_key_id,
        aws_secret_access_key=cfg.s3_secret_access_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if cfg.s3_force_path_style else "virtual"},
        ),
    )
