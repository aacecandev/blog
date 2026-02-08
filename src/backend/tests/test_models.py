"""Tests for Pydantic models and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..models import PostDetail, PostMeta, PostSummary, PostListResponse


class TestPostMeta:
    """Tests for PostMeta model."""

    def test_valid_slug(self) -> None:
        """Should accept valid slug formats."""
        valid_slugs = [
            "my-post",
            "my_post",
            "mypost",
            "MyPost123",
            "post-123",
            "a",
            "a-b-c-d-e",
        ]
        for slug in valid_slugs:
            meta = PostMeta(slug=slug, title="Test", date="2024-01-01")
            assert meta.slug == slug

    def test_invalid_slug_empty(self) -> None:
        """Should reject empty slug."""
        with pytest.raises(ValidationError) as exc_info:
            PostMeta(slug="", title="Test", date="2024-01-01")
        assert "Slug cannot be empty" in str(exc_info.value)

    def test_invalid_slug_special_chars(self) -> None:
        """Should reject slugs with special characters."""
        invalid_slugs = [
            "../etc/passwd",
            "test<script>",
            "test/post",
            "test post",
            "test.post",
            "test@post",
            "test#post",
        ]
        for slug in invalid_slugs:
            with pytest.raises(ValidationError):
                PostMeta(slug=slug, title="Test", date="2024-01-01")

    def test_invalid_slug_too_long(self) -> None:
        """Should reject slugs exceeding max length."""
        long_slug = "a" * 201
        with pytest.raises(ValidationError) as exc_info:
            PostMeta(slug=long_slug, title="Test", date="2024-01-01")
        assert "too long" in str(exc_info.value)

    def test_optional_fields(self) -> None:
        """Optional fields should have proper defaults."""
        meta = PostMeta(slug="test", title="Test", date="2024-01-01")
        assert meta.description is None
        assert meta.tags == []

    def test_tags_list(self) -> None:
        """Tags should be stored as a list."""
        meta = PostMeta(
            slug="test",
            title="Test",
            date="2024-01-01",
            tags=["python", "testing"],
        )
        assert meta.tags == ["python", "testing"]


class TestPostSummary:
    """Tests for PostSummary (alias of PostMeta)."""

    def test_post_summary_is_post_meta(self) -> None:
        """PostSummary should be the same as PostMeta."""
        summary = PostSummary(slug="test", title="Test", date="2024-01-01")
        assert isinstance(summary, PostMeta)


class TestPostDetail:
    """Tests for PostDetail model."""

    def test_valid_post_detail(self) -> None:
        """Should create valid PostDetail."""
        meta = PostMeta(slug="test", title="Test", date="2024-01-01")
        detail = PostDetail(meta=meta, content="# Hello World")
        assert detail.meta == meta
        assert detail.content == "# Hello World"

    def test_nested_meta_validation(self) -> None:
        """PostDetail should validate nested meta."""
        with pytest.raises(ValidationError):
            PostDetail(
                meta={"slug": "../invalid", "title": "Test", "date": "2024-01-01"},
                content="Content",
            )


class TestPostListResponse:
    """Tests for PostListResponse model."""

    def test_valid_response(self) -> None:
        """Should create valid paginated response."""
        posts = [
            PostSummary(slug="post-1", title="Post 1", date="2024-01-02"),
            PostSummary(slug="post-2", title="Post 2", date="2024-01-01"),
        ]
        response = PostListResponse(posts=posts, total=10, limit=2, offset=0)
        assert len(response.posts) == 2
        assert response.total == 10
        assert response.limit == 2
        assert response.offset == 0

    def test_empty_posts_list(self) -> None:
        """Should handle empty posts list."""
        response = PostListResponse(posts=[], total=0, limit=20, offset=0)
        assert response.posts == []
        assert response.total == 0
