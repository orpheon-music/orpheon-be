from io import BytesIO

import boto3
from botocore.config import Config


class S3Service:
    def __init__(
        self,
        secret_key: str,
        access_key: str,
        region: str,
        endpoint_url: str,
    ):
        self.endpoint_url = endpoint_url

        self.client = boto3.client(  # type: ignore
            "s3",
            aws_secret_access_key=secret_key,
            aws_access_key_id=access_key,
            region_name=region,
            endpoint_url=endpoint_url,
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

        return f"{self.endpoint_url}/{bucket}/{file_name}"

    async def get_presigned_url(
        self, bucket: str, file_name: str, expiration: int = 3600
    ) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": file_name},
            ExpiresIn=expiration,
        )
