"""Pytest fixtures and configuration for backend tests."""

from __future__ import annotations

import os
import tempfile
from typing import Generator

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_s3

# Set test environment before importing app modules
os.environ["DEV_BLOG_ENVIRONMENT"] = "local"
os.environ["DEV_BLOG_S3_BUCKET"] = "test-bucket"
os.environ["DEV_BLOG_CACHE_TTL_SECONDS"] = "60"


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Create a FastAPI test client."""
    # Import here to ensure environment is set first
    from ..main import app
    from ..cache import clear_all_caches

    clear_all_caches()
    with TestClient(app) as client:
        yield client
    clear_all_caches()


@pytest.fixture
def temp_content_dir() -> Generator[str, None, None]:
    """Create a temporary directory with test Markdown files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create sample blog posts
        post1 = """---
title: Test Post One
date: 2024-01-15
description: This is the first test post
tags:
  - python
  - testing
---

# Test Post One

This is the content of the first test post.
"""
        post2 = """---
title: Test Post Two
date: 2024-01-10
description: This is the second test post
tags:
  - fastapi
---

# Test Post Two

This is the content of the second test post.
"""
        post3_invalid = """---
title: Invalid YAML Post
date: 2024-01-05
tags: [unclosed bracket
---

Invalid frontmatter content.
"""

        # Write test files
        with open(os.path.join(tmpdir, "test-post-one.md"), "w") as f:
            f.write(post1)
        with open(os.path.join(tmpdir, "test-post-two.md"), "w") as f:
            f.write(post2)
        with open(os.path.join(tmpdir, "invalid-yaml.md"), "w") as f:
            f.write(post3_invalid)

        yield tmpdir


@pytest.fixture
def local_content_client(temp_content_dir: str) -> Generator[TestClient, None, None]:
    """Create a test client with local content directory configured."""
    os.environ["DEV_BLOG_CONTENT_DIR"] = temp_content_dir
    os.environ["DEV_BLOG_S3_BUCKET"] = ""

    # Re-import to pick up new settings
    # Note: In real tests, you might need to reload the settings module
    from ..main import app
    from ..cache import clear_all_caches
    from ..config import settings

    # Override settings for this test
    object.__setattr__(settings, "content_dir", temp_content_dir)
    object.__setattr__(settings, "s3_bucket", "")

    clear_all_caches()
    with TestClient(app) as client:
        yield client
    clear_all_caches()

    # Reset environment
    os.environ.pop("DEV_BLOG_CONTENT_DIR", None)


@pytest.fixture
def mock_s3_fixture() -> Generator[None, None, None]:
    """Mock AWS S3 for testing."""
    with mock_s3():
        # Create test bucket and objects
        s3 = boto3.client("s3", region_name="eu-west-1")
        s3.create_bucket(
            Bucket="test-bucket",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )

        # Add test posts
        post1 = """---
title: S3 Test Post
date: 2024-01-20
description: A post stored in S3
tags:
  - aws
  - s3
---

# S3 Test Post

Content from S3.
"""
        s3.put_object(
            Bucket="test-bucket",
            Key="posts/s3-test-post.md",
            Body=post1.encode("utf-8"),
        )

        yield


@pytest.fixture
def sample_post_content() -> str:
    """Return sample valid Markdown post content."""
    return """---
title: Sample Post
date: 2024-01-01
description: A sample post for testing
tags:
  - test
---

# Sample Post

This is sample content.
"""


@pytest.fixture
def invalid_yaml_content() -> str:
    """Return Markdown with invalid YAML frontmatter."""
    return """---
title: Bad Post
date: [invalid yaml
---

Content here.
"""
