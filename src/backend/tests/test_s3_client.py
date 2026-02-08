"""Tests for S3 client functionality."""

from __future__ import annotations

import boto3
import pytest
from moto import mock_s3

from ..s3_client import (
    S3Error,
    get_object_text,
    get_s3_client,
    get_slug_to_key_map,
    list_markdown_keys,
    reset_s3_client,
)

# Test bucket name
TEST_BUCKET = "test-bucket"
TEST_REGION = "eu-west-1"


@pytest.fixture(autouse=True)
def reset_client_and_settings() -> None:
    """Reset S3 client and configure test settings before each test."""
    from ..config import settings

    reset_s3_client()
    # Set test bucket name on settings
    object.__setattr__(settings, "s3_bucket", TEST_BUCKET)
    object.__setattr__(settings, "aws_region", TEST_REGION)


class TestS3Client:
    """Tests for S3 client singleton."""

    @mock_s3
    def test_get_s3_client_singleton(self) -> None:
        """S3 client should be a singleton."""
        client1 = get_s3_client()
        client2 = get_s3_client()
        assert client1 is client2

    @mock_s3
    def test_reset_s3_client(self) -> None:
        """Reset should create new client on next call."""
        client1 = get_s3_client()
        reset_s3_client()
        client2 = get_s3_client()
        assert client1 is not client2


class TestListMarkdownKeys:
    """Tests for listing Markdown keys from S3."""

    @mock_s3
    def test_list_keys_empty_bucket(self) -> None:
        """Should return empty list for empty bucket."""
        # Create bucket
        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": TEST_REGION},
        )

        keys = list_markdown_keys()
        assert keys == []

    @mock_s3
    def test_list_keys_with_markdown_files(self) -> None:
        """Should list only .md files."""
        # Create bucket with mixed files
        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": TEST_REGION},
        )
        s3.put_object(Bucket=TEST_BUCKET, Key="posts/post1.md", Body=b"content")
        s3.put_object(Bucket=TEST_BUCKET, Key="posts/post2.md", Body=b"content")
        s3.put_object(Bucket=TEST_BUCKET, Key="posts/image.png", Body=b"binary")

        keys = list_markdown_keys()
        assert len(keys) == 2
        assert all(k.endswith(".md") for k in keys)

    @mock_s3
    def test_list_keys_nonexistent_bucket(self) -> None:
        """Should raise S3Error for nonexistent bucket."""
        from ..config import settings

        object.__setattr__(settings, "s3_bucket", "nonexistent-bucket-12345")

        with pytest.raises(S3Error):
            list_markdown_keys()


class TestGetObjectText:
    """Tests for retrieving object content."""

    @mock_s3
    def test_get_object_success(self) -> None:
        """Should retrieve object content as text."""
        # Create bucket and object
        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": TEST_REGION},
        )
        content = "---\ntitle: Test\n---\n# Hello"
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="posts/test.md",
            Body=content.encode("utf-8"),
        )

        result = get_object_text("posts/test.md")
        assert result == content

    @mock_s3
    def test_get_object_not_found(self) -> None:
        """Should raise FileNotFoundError for missing object."""
        # Create empty bucket
        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": TEST_REGION},
        )

        with pytest.raises(FileNotFoundError):
            get_object_text("posts/nonexistent.md")


class TestGetSlugToKeyMap:
    """Tests for slug-to-key mapping."""

    @mock_s3
    def test_builds_slug_map(self) -> None:
        """Should build correct slug-to-key mapping."""
        from ..cache import clear_all_caches

        clear_all_caches()

        # Create bucket with posts
        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": TEST_REGION},
        )
        s3.put_object(Bucket=TEST_BUCKET, Key="posts/my-post.md", Body=b"content")
        s3.put_object(Bucket=TEST_BUCKET, Key="posts/another-post.md", Body=b"content")

        slug_map = get_slug_to_key_map()
        assert "my-post" in slug_map
        assert "another-post" in slug_map
        assert slug_map["my-post"] == "posts/my-post.md"

    @mock_s3
    def test_slug_map_cached(self) -> None:
        """Slug map should be cached."""
        from ..cache import clear_all_caches, get_slug_map_cached

        clear_all_caches()

        # Create bucket
        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": TEST_REGION},
        )
        s3.put_object(Bucket=TEST_BUCKET, Key="posts/test.md", Body=b"content")

        # First call builds cache
        map1 = get_slug_to_key_map()
        assert get_slug_map_cached() is not None

        # Second call should return cached
        map2 = get_slug_to_key_map()
        assert map1 == map2
