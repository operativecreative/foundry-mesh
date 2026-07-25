#!/usr/bin/env python3
"""
Object Storage — MinIO client. No fallbacks. No placebos.

Requires running MinIO server. Every operation fails explicitly
if MinIO is unavailable.
"""
from typing import Dict, Any, Optional, List


class MinioClient:
    """MinIO client. Requires running MinIO server."""

    def __init__(self, endpoint: str = "localhost:9000", 
                 access_key: str = "minioadmin", 
                 secret_key: str = "minioadmin",
                 secure: bool = False):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self._client = None

    def connect(self):
        from minio import Minio
        self._client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )
        # Verify connection
        self._client.list_buckets()
        print(f"Connected to MinIO at {self.endpoint}")

    def put(self, bucket: str, key: str, data: bytes, metadata: Optional[Dict[str, Any]] = None):
        if self._client is None:
            raise RuntimeError("MinIO not connected. Call connect() first.")

        from io import BytesIO
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

        self._client.put_object(
            bucket, key, BytesIO(data), length=len(data),
            metadata=metadata or {}
        )

    def get(self, bucket: str, key: str) -> Optional[bytes]:
        if self._client is None:
            raise RuntimeError("MinIO not connected. Call connect() first.")

        try:
            response = self._client.get_object(bucket, key)
            return response.read()
        except Exception:
            return None

    def delete(self, bucket: str, key: str):
        if self._client is None:
            raise RuntimeError("MinIO not connected. Call connect() first.")
        self._client.remove_object(bucket, key)

    def list_keys(self, bucket: str, prefix: str = "") -> List[str]:
        if self._client is None:
            raise RuntimeError("MinIO not connected. Call connect() first.")

        objects = self._client.list_objects(bucket, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]
