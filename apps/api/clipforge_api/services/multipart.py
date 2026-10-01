import math
from typing import Any

from botocore.exceptions import ClientError


def uploaded_parts(
    client: Any, bucket: str, key: str, upload_id: str, size: int
) -> list[dict[str, Any]] | None:
    """Return stored parts, or None when storage already completed this upload."""
    parts = []
    try:
        for page in client.get_paginator("list_parts").paginate(
            Bucket=bucket, Key=key, UploadId=upload_id
        ):
            parts.extend(page.get("Parts", []))
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchUpload":
            raise
        try:
            stored = client.head_object(Bucket=bucket, Key=key)
        except ClientError as stored_error:
            if stored_error.response["Error"]["Code"] not in {"404", "NoSuchKey", "NotFound"}:
                raise
            raise ValueError(
                "Upload no longer exists. Cancel it and upload the source again."
            ) from None
        if stored["ContentLength"] != size:
            raise ValueError("Stored video size does not match the upload.") from None
        return None
    return parts


def discard(client: Any, bucket: str, key: str, upload_id: str) -> None:
    """Remove both unfinished parts and an object finalized before a failed DB commit."""
    try:
        client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchUpload":
            raise
    client.delete_object(Bucket=bucket, Key=key)


def finalize(client: Any, bucket: str, key: str, upload_id: str, size: int, part_size: int) -> None:
    """Recover a completed S3 upload if the subsequent database commit was interrupted."""
    parts = uploaded_parts(client, bucket, key, upload_id, size)
    if parts is None:
        return
    if len(parts) != math.ceil(size / part_size) or sum(p["Size"] for p in parts) != size:
        raise ValueError("The upload is incomplete. Retry the missing parts.")
    for index, part in enumerate(parts):
        expected = min(part_size, size - index * part_size)
        if part["PartNumber"] != index + 1 or part["Size"] != expected:
            raise ValueError("Upload parts do not match the declared file.")
    client.complete_multipart_upload(
        Bucket=bucket,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={
            "Parts": [{"PartNumber": p["PartNumber"], "ETag": p["ETag"]} for p in parts]
        },
    )
