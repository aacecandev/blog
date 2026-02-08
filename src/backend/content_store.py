"""Content storage abstraction for blog posts.

This module provides a unified interface for loading blog content from
either local filesystem (development) or S3 (production), with proper
validation and error handling.
"""

from __future__ import annotations

import os
import re

from .config import logger, settings
from .s3_client import S3Error, get_object_text, get_slug_to_key_map

# Slug validation pattern (must match models.py)
SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_SLUG_LENGTH = 200


class ContentError(Exception):
    """Custom exception for content operations."""

    pass


def validate_slug(slug: str) -> str:
    """Validate slug format to prevent path traversal attacks.

    Args:
        slug: The slug to validate.

    Returns:
        The validated slug.

    Raises:
        ValueError: If slug format is invalid.
    """
    if not slug:
        raise ValueError("Slug cannot be empty")
    if len(slug) > MAX_SLUG_LENGTH:
        raise ValueError(f"Slug too long (max {MAX_SLUG_LENGTH} characters)")
    if not SLUG_PATTERN.match(slug):
        raise ValueError(
            "Invalid slug format. Use only alphanumeric characters, hyphens, and underscores."
        )
    return slug


def list_post_slugs() -> list[str]:
    """List all available blog post slugs.

    Returns slugs from either local filesystem or S3 depending on configuration.

    Returns:
        List of post slug strings (filename without .md extension).

    Raises:
        ContentError: If listing fails due to storage errors.
    """
    if settings.content_dir:
        return _list_local_slugs()
    return _list_s3_slugs()


def _list_local_slugs() -> list[str]:
    """List post slugs from local filesystem.

    Returns:
        List of slugs from Markdown files in content_dir.
    """
    directory = settings.content_dir
    if not os.path.isdir(directory):
        logger.warning("Content directory does not exist: %s", directory)
        return []

    slugs: list[str] = []
    try:
        for name in os.listdir(directory):
            if not name.lower().endswith(".md"):
                continue
            slug = name.rsplit(".", 1)[0]
            # Validate slug format
            if SLUG_PATTERN.match(slug):
                slugs.append(slug)
            else:
                logger.warning("Skipping file with invalid slug format: %s", name)

        logger.debug("Found %d posts in local directory", len(slugs))
        return slugs

    except OSError as e:
        logger.error("Failed to list local content directory: %s", str(e))
        raise ContentError(f"Failed to list content directory: {str(e)}") from e


def _list_s3_slugs() -> list[str]:
    """List post slugs from S3 bucket.

    Returns:
        List of slugs from Markdown files in S3.
    """
    try:
        slug_map = get_slug_to_key_map()
        return list(slug_map.keys())
    except S3Error as e:
        logger.error("Failed to list posts from S3: %s", str(e))
        raise ContentError(f"Failed to list posts from S3: {str(e)}") from e


def load_post_by_slug(slug: str) -> str:
    """Load raw Markdown content for a post by its slug.

    Args:
        slug: URL-safe identifier for the post.

    Returns:
        Raw Markdown content including frontmatter.

    Raises:
        ValueError: If slug format is invalid.
        FileNotFoundError: If post does not exist.
        ContentError: If loading fails due to storage errors.
    """
    # Validate slug to prevent path traversal
    validate_slug(slug)

    if settings.content_dir:
        return _load_local_post(slug)
    return _load_s3_post(slug)


def _load_local_post(slug: str) -> str:
    """Load post from local filesystem.

    Args:
        slug: Validated post slug.

    Returns:
        Raw Markdown content.

    Raises:
        FileNotFoundError: If file does not exist.
        ContentError: If file cannot be read.
    """
    path = os.path.join(settings.content_dir, f"{slug}.md")

    # Extra safety check - ensure path doesn't escape content_dir
    real_path = os.path.realpath(path)
    real_content_dir = os.path.realpath(settings.content_dir)
    if not real_path.startswith(real_content_dir):
        logger.error("Path traversal attempt detected: %s", slug)
        raise ValueError("Invalid slug")

    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        logger.debug("Loaded post from local file: %s", path)
        return content

    except FileNotFoundError:
        logger.debug("Post not found locally: %s", slug)
        raise

    except OSError as e:
        logger.error("Failed to read local post %s: %s", slug, str(e))
        raise ContentError(f"Failed to read post: {str(e)}") from e


def _load_s3_post(slug: str) -> str:
    """Load post from S3 bucket.

    Args:
        slug: Validated post slug.

    Returns:
        Raw Markdown content.

    Raises:
        FileNotFoundError: If post does not exist in S3.
        ContentError: If S3 operation fails.
    """
    try:
        slug_map = get_slug_to_key_map()
        key = slug_map.get(slug)

        if not key:
            logger.debug("Post not found in S3: %s", slug)
            raise FileNotFoundError(slug)

        content = get_object_text(key)
        logger.debug("Loaded post from S3: %s", key)
        return content

    except S3Error as e:
        logger.error("Failed to load post %s from S3: %s", slug, str(e))
        raise ContentError(f"Failed to load post from S3: {str(e)}") from e
