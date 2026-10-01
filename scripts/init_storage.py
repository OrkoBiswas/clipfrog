from botocore.exceptions import ClientError
from clipforge_api.config import settings
from clipforge_api.storage import s3

client = s3()
try:
    client.head_bucket(Bucket=settings().s3_bucket)
except ClientError as error:
    if error.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
        raise
    client.create_bucket(Bucket=settings().s3_bucket)
print("Private media bucket ready")
