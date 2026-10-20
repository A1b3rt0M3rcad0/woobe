from shared.contracts.object_storage import ObjectStorageError
from shared.infra.object_storage.s3 import S3ObjectStorage


def create_s3_object_storage(*, bucket, region=None, prefix='', endpoint_url=None,
                             force_path_style=False, server_side_encryption=None,
                             legacy_keys=False):
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client('s3', region_name=region, endpoint_url=endpoint_url or None,
            config=Config(signature_version='s3v4', s3={
                'addressing_style': 'path' if force_path_style else 'auto'},
                connect_timeout=10, read_timeout=30, max_pool_connections=8,
                retries={'mode': 'standard', 'max_attempts': 2}))
        return S3ObjectStorage(client, bucket=bucket, prefix=prefix, legacy_keys=legacy_keys,
                                server_side_encryption=server_side_encryption)
    except Exception as error:
        raise ObjectStorageError('unavailable', 'S3 configuration or credentials are unavailable') from error
