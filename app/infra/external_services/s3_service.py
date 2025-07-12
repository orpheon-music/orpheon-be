from io import BytesIO

import boto3
from botocore.config import Config

from app.config.settings import get_settings

settings = get_settings()


class S3Service:
    def __init__(self):
        self.client = boto3.client(  # type: ignore
            "s3",
            aws_access_key_id=settings.AWS_S3_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_S3_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION,
            endpoint_url=settings.AWS_S3_URL,
            config=Config(
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    async def upload_file(
        self, file_content: BytesIO, file_name: str, bucket: str
    ) -> str:
        self.client.upload_fileobj(
            file_content,
            bucket,
            file_name,
            ExtraArgs={"ACL": "public-read"},
        )
        return f"{settings.AWS_S3_URL}/{bucket}/{file_name}"
