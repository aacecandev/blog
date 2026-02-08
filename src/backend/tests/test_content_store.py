"""Tests for content storage functionality."""

from __future__ import annotations

import os
import tempfile

import pytest

from ..content_store import (
    ContentError,
    list_post_slugs,
    load_post_by_slug,
    validate_slug,
)


class TestValidateSlug:
    """Tests for slug validation function."""

    def test_valid_slugs(self) -> None:
        """Should accept valid slug formats."""
        valid_slugs = ["my-post", "my_post", "mypost123", "A-B-C"]
        for slug in valid_slugs:
            assert validate_slug(slug) == slug

    def test_empty_slug(self) -> None:
        """Should reject empty slug."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_slug("")

    def test_long_slug(self) -> None:
        """Should reject overly long slugs."""
        long_slug = "a" * 201
        with pytest.raises(ValueError, match="too long"):
            validate_slug(long_slug)

    def test_invalid_characters(self) -> None:
        """Should reject slugs with invalid characters."""
        invalid_slugs = [
            "../etc/passwd",
            "test/post",
            "test post",
            "test.post",
            "test<script>",
        ]
        for slug in invalid_slugs:
            with pytest.raises(ValueError, match="Invalid slug format"):
                validate_slug(slug)


class TestListPostSlugs:
    """Tests for listing post slugs."""

    def test_list_local_slugs(self, temp_content_dir: str) -> None:
        """Should list slugs from local directory."""
        from ..config import settings

        # Temporarily set content_dir
        original = settings.content_dir
        object.__setattr__(settings, "content_dir", temp_content_dir)
        object.__setattr__(settings, "s3_bucket", "")

        try:
            slugs = list_post_slugs()
            assert isinstance(slugs, list)
            assert "test-post-one" in slugs
            assert "test-post-two" in slugs
        finally:
            object.__setattr__(settings, "content_dir", original)

    def test_list_nonexistent_directory(self) -> None:
        """Should return empty list for nonexistent directory."""
        from ..config import settings

        original = settings.content_dir
        object.__setattr__(settings, "content_dir", "/nonexistent/path")
        object.__setattr__(settings, "s3_bucket", "")

        try:
            slugs = list_post_slugs()
            assert slugs == []
        finally:
            object.__setattr__(settings, "content_dir", original)

    def test_filters_invalid_slugs(self) -> None:
        """Should filter out files with invalid slug names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with invalid slug format
            with open(os.path.join(tmpdir, "invalid slug.md"), "w") as f:
                f.write("---\ntitle: Test\n---\nContent")
            with open(os.path.join(tmpdir, "valid-slug.md"), "w") as f:
                f.write("---\ntitle: Test\n---\nContent")

            from ..config import settings

            original = settings.content_dir
            object.__setattr__(settings, "content_dir", tmpdir)
            object.__setattr__(settings, "s3_bucket", "")

            try:
                slugs = list_post_slugs()
                assert "valid-slug" in slugs
                assert "invalid slug" not in slugs
            finally:
                object.__setattr__(settings, "content_dir", original)


class TestLoadPostBySlug:
    """Tests for loading individual posts."""

    def test_load_existing_post(self, temp_content_dir: str) -> None:
        """Should load content of existing post."""
        from ..config import settings

        original = settings.content_dir
        object.__setattr__(settings, "content_dir", temp_content_dir)
        object.__setattr__(settings, "s3_bucket", "")

        try:
            content = load_post_by_slug("test-post-one")
            assert "Test Post One" in content
            assert "title:" in content
        finally:
            object.__setattr__(settings, "content_dir", original)

    def test_load_nonexistent_post(self, temp_content_dir: str) -> None:
        """Should raise FileNotFoundError for nonexistent post."""
        from ..config import settings

        original = settings.content_dir
        object.__setattr__(settings, "content_dir", temp_content_dir)
        object.__setattr__(settings, "s3_bucket", "")

        try:
            with pytest.raises(FileNotFoundError):
                load_post_by_slug("nonexistent-post")
        finally:
            object.__setattr__(settings, "content_dir", original)

    def test_path_traversal_blocked(self, temp_content_dir: str) -> None:
        """Should block path traversal attempts."""
        from ..config import settings

        original = settings.content_dir
        object.__setattr__(settings, "content_dir", temp_content_dir)
        object.__setattr__(settings, "s3_bucket", "")

        try:
            with pytest.raises(ValueError):
                load_post_by_slug("../../../etc/passwd")
        finally:
            object.__setattr__(settings, "content_dir", original)

    def test_validates_slug_before_loading(self) -> None:
        """Should validate slug format before attempting to load."""
        with pytest.raises(ValueError, match="Invalid slug format"):
            load_post_by_slug("test/../../etc/passwd")
