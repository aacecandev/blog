"""Pydantic models for the blog API.

This module defines the data models used for API requests and responses,
including validation for security-sensitive fields like slugs.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

# Slug validation pattern: alphanumeric, hyphens, underscores only
SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class PostMeta(BaseModel):
    """Metadata for a blog post.

    Attributes:
        slug: URL-safe identifier for the post.
        title: Display title of the post.
        date: Publication date (ISO-8601 recommended).
        description: Optional short description/excerpt.
        tags: List of tags/categories for the post.
    """

    slug: str
    title: str
    date: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Validate slug format to prevent path traversal attacks."""
        if not v:
            raise ValueError("Slug cannot be empty")
        if len(v) > 200:
            raise ValueError("Slug too long (max 200 characters)")
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "Invalid slug format. Use only alphanumeric characters, hyphens, and underscores."
            )
        return v


# PostSummary is an alias for PostMeta (same structure)
PostSummary = PostMeta


class PostDetail(BaseModel):
    """Full blog post with content.

    Attributes:
        meta: Post metadata (title, date, tags, etc.).
        content: Full Markdown content of the post.
    """

    meta: PostMeta
    content: str


class PostListResponse(BaseModel):
    """Paginated response for post listings.

    Attributes:
        posts: List of post summaries for this page.
        total: Total number of posts available.
        limit: Maximum posts per page.
        offset: Number of posts skipped.
    """

    posts: list[PostSummary]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    """Health check response.

    Attributes:
        status: Service status ('ok' or 'degraded').
        version: API version string.
    """

    status: str
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    """Standard error response.

    Attributes:
        detail: Human-readable error message.
        error_code: Machine-readable error code.
    """

    detail: str
    error_code: str | None = None


# Type alias for validated slug parameter
ValidatedSlug = Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]+$", max_length=200)]
