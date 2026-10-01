from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from clipforge_api.services.multipart import discard, finalize, uploaded_parts


def storage_error(code):
    return ClientError({"Error": {"Code": code, "Message": code}}, "ListParts")


def completed_storage(size=10):
    storage = Mock()
    storage.get_paginator.return_value.paginate.side_effect = storage_error("NoSuchUpload")
    storage.head_object.return_value = {"ContentLength": size}
    return storage


def test_finalize_recovers_storage_completion_without_repeating_it():
    storage = completed_storage()
    finalize(storage, "bucket", "key", "upload", 10, 8)
    storage.complete_multipart_upload.assert_not_called()


@pytest.mark.parametrize(
    "parts",
    [
        [{"PartNumber": 1, "Size": 8, "ETag": "first"}],
        [{"PartNumber": 1, "Size": 7}, {"PartNumber": 2, "Size": 3}],
        [{"PartNumber": 1, "Size": 8}, {"PartNumber": 3, "Size": 2}],
    ],
)
def test_finalize_rejects_missing_wrong_size_and_nonsequential_parts(parts):
    storage = Mock()
    storage.get_paginator.return_value.paginate.return_value = [{"Parts": parts}]
    with pytest.raises(ValueError):
        finalize(storage, "bucket", "key", "upload", 10, 8)
    storage.complete_multipart_upload.assert_not_called()


def test_finalize_uses_all_storage_pages():
    storage = Mock()
    storage.get_paginator.return_value.paginate.return_value = [
        {"Parts": [{"PartNumber": 1, "Size": 8, "ETag": "first"}]},
        {"Parts": [{"PartNumber": 2, "Size": 2, "ETag": "last"}]},
    ]
    finalize(storage, "bucket", "key", "upload", 10, 8)
    assert storage.complete_multipart_upload.call_args.kwargs["MultipartUpload"] == {
        "Parts": [{"PartNumber": 1, "ETag": "first"}, {"PartNumber": 2, "ETag": "last"}]
    }


def test_recovery_rejects_size_mismatch_and_preserves_storage_errors():
    storage = completed_storage(9)
    with pytest.raises(ValueError, match="size"):
        uploaded_parts(storage, "bucket", "key", "upload", 10)
    storage.head_object.side_effect = storage_error("AccessDenied")
    with pytest.raises(ClientError):
        uploaded_parts(storage, "bucket", "key", "upload", 10)


def test_discard_removes_object_left_by_interrupted_completion():
    storage = completed_storage()
    storage.abort_multipart_upload.side_effect = storage_error("NoSuchUpload")
    discard(storage, "bucket", "key", "upload")
    storage.delete_object.assert_called_once_with(Bucket="bucket", Key="key")


def test_browser_resume_recovers_completed_storage_and_queues_once(client, monkeypatch):
    storage = completed_storage()
    storage.create_multipart_upload.return_value = {"UploadId": "storage-upload"}
    monkeypatch.setattr("clipforge_api.routes.uploads.s3", lambda **kwargs: storage)
    dispatch = Mock()
    monkeypatch.setattr("clipforge_api.routes.uploads.celery.send_task", dispatch)
    client.post(
        "/api/v1/auth/register",
        json={"email": "resume@example.com", "name": "Resume", "password": "long-enough-password"},
    ).raise_for_status()
    project = client.post("/api/v1/projects", json={"name": "Interrupted completion"}).json()
    base = f"/api/v1/projects/{project['id']}/upload"
    response = client.post(
        f"{base}/initiate",
        json={"filename": "source.mp4", "size_bytes": 10, "mime_type": "video/mp4"},
    )
    response.raise_for_status()
    upload = f"{base}/{response.json()['id']}"
    status = client.get(upload)
    assert status.status_code == 200
    assert status.json()["parts"] == [{"number": 1, "size": 10}]
    first = client.post(f"{upload}/complete")
    assert first.status_code == 200
    assert client.post(f"{upload}/complete").json()["job_id"] == first.json()["job_id"]
    dispatch.assert_called_once()
    storage.complete_multipart_upload.assert_not_called()
