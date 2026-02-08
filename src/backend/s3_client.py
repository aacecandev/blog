"""AWS S3 client utilities for blog content storage.

This module provides S3 operations with singleton client pattern,
comprehensive error handling, and caching of slug-to-key mappings.
"""

from __future__ import annotations

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError

from .cache import get_slug_map_cached, set_slug_map_cached
from .config import logger, settings

# Singleton S3 client instance
_s3_client: BaseClient | None = None


class S3Error(Exception):
    """Custom exception for S3 operations."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


def get_s3_client() -> BaseClient:
    """Get or create singleton S3 client.

    Returns:
        Configured boto3 S3 client instance.

    Note:
        Uses singleton pattern to avoid creating multiple clients.
    """
    global _s3_client
    if _s3_client is None:
        logger.debug("Creating new S3 client for region: %s", settings.aws_region)
        _s3_client = boto3.client("s3", region_name=settings.aws_region)
    return _s3_client


def reset_s3_client() -> None:
    """Reset the singleton S3 client. Useful for testing."""
    global _s3_client
    _s3_client = None
    logger.debug("S3 client reset")


def list_markdown_keys(prefix: str | None = None) -> list[str]:
    """List all Markdown file keys in the S3 bucket.

    Args:
        prefix: Optional S3 prefix to filter results. Defaults to settings.s3_prefix.

    Returns:
        List of S3 keys ending in .md extension.

    Raises:
        S3Error: If S3 operation fails.
    """
    client = get_s3_client()
    bucket = settings.s3_bucket
    effective_prefix = prefix if prefix is not None else settings.s3_prefix

    if not bucket:
        logger.warning("S3 bucket not configured")
        return []

    try:
        paginator = client.get_paginator("list_objects_v2")
        keys: list[str] = []

        logger.debug("Listing S3 keys in bucket=%s, prefix=%s", bucket, effective_prefix)

        for page in paginator.paginate(Bucket=bucket, Prefix=effective_prefix):
            for obj in page.get("Contents", []) or []:
                key = obj["Key"]
                if key.lower().endswith(".md"):
                    keys.append(key)

        logger.debug("Found %d Markdown files in S3", len(keys))
        return keys

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))

        if error_code == "NoSuchBucket":
            logger.error("S3 bucket does not exist: %s", bucket)
        elif error_code == "AccessDenied":
            logger.error("Access denied to S3 bucket: %s", bucket)
        else:
            logger.error("S3 ClientError (%s): %s", error_code, error_msg)

        raise S3Error(f"Failed to list S3 objects: {error_msg}", e) from e

    except BotoCoreError as e:
        logger.error("AWS connectivity error: %s", str(e))
        raise S3Error(f"AWS connectivity error: {str(e)}", e) from e


def get_object_text(key: str) -> str:
    """Retrieve text content of an S3 object.

    Args:
        key: Full S3 key path to the object.

    Returns:
        UTF-8 decoded content of the object.

    Raises:
        S3Error: If object retrieval fails.
        FileNotFoundError: If the object does not exist.
    """
    client = get_s3_client()
    bucket = settings.s3_bucket

    if not bucket:
        raise S3Error("S3 bucket not configured")

    try:
        logger.debug("Fetching S3 object: s3://%s/%s", bucket, key)
        res = client.get_object(Bucket=bucket, Key=key)
        body = res["Body"].read()
        return body.decode("utf-8")

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")

        if error_code == "NoSuchKey":
            logger.warning("S3 object not found: %s", key)
            raise FileNotFoundError(f"S3 object not found: {key}") from e

        logger.error("S3 error fetching %s: %s", key, str(e))
        raise S3Error(f"Failed to fetch S3 object: {key}", e) from e

    except BotoCoreError as e:
        logger.error("AWS connectivity error fetching %s: %s", key, str(e))
        raise S3Error(f"AWS connectivity error: {str(e)}", e) from e

    except UnicodeDecodeError as e:
        logger.error("Failed to decode S3 object as UTF-8: %s", key)
        raise S3Error(f"Failed to decode object as UTF-8: {key}", e) from e


def get_slug_to_key_map() -> dict[str, str]:
    """Get mapping of post slugs to their S3 keys.

    Uses caching to avoid repeated S3 list operations.

    Returns:
        Dictionary mapping slug strings to full S3 key paths.

    Raises:
        S3Error: If S3 list operation fails.
    """
    # Check cache first
    cached = get_slug_map_cached()
    if cached is not None:
        return cached

    # Build mapping from S3 keys
    keys = list_markdown_keys()
    slug_map: dict[str, str] = {}

    for key in keys:
        # Extract slug from key: "posts/my-post.md" -> "my-post"
        filename = key.split("/")[-1]
        if filename.lower().endswith(".md"):
            slug = filename.rsplit(".", 1)[0]
            slug_map[slug] = key

    # Cache the mapping
    set_slug_map_cached(slug_map)
    logger.debug("Built slug-to-key map with %d entries", len(slug_map))

    return slug_map
