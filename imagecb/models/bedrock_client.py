"""Shared Bedrock client.

Cached boto3 client for ``bedrock-runtime`` (converse, invoke_model, rerank).
Auth is implicit: boto3 picks up ``AWS_BEARER_TOKEN_BEDROCK`` (loaded from
``.env`` via ``imagecb.config``) or any standard AWS credential source.
"""

from __future__ import annotations

from typing import Any, Optional

from imagecb.config import SETTINGS


_client: Optional[Any] = None


def get_bedrock_runtime() -> Any:
    global _client
    if _client is None:
        import boto3

        _client = boto3.client("bedrock-runtime", region_name=SETTINGS.aws_region)
    return _client
