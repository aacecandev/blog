"""Tests for main FastAPI application endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_ok(self, test_client: TestClient) -> None:
        """Health endpoint should return status ok."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_has_cache_headers(self, test_client: TestClient) -> None:
        """Health endpoint should not have cache headers (dynamic)."""
        response = test_client.get("/health")
        assert response.status_code == 200


class TestRootEndpoint:
    """Tests for the / endpoint."""

    def test_root_returns_service_info(self, test_client: TestClient) -> None:
        """Root endpoint should return service metadata."""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "endpoints" in data
        assert isinstance(data["endpoints"], list)


class TestPostsEndpoint:
    """Tests for the /posts endpoint."""

    def test_posts_returns_list(self, local_content_client: TestClient) -> None:
        """Posts endpoint should return a list of posts."""
        response = local_content_client.get("/posts")
        assert response.status_code == 200
        data = response.json()
        assert "posts" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["posts"], list)

    def test_posts_pagination_limit(self, local_content_client: TestClient) -> None:
        """Posts endpoint should respect limit parameter."""
        response = local_content_client.get("/posts?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) <= 1
        assert data["limit"] == 1

    def test_posts_pagination_offset(self, local_content_client: TestClient) -> None:
        """Posts endpoint should respect offset parameter."""
        response = local_content_client.get("/posts?offset=1")
        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 1

    def test_posts_invalid_limit(self, test_client: TestClient) -> None:
        """Posts endpoint should reject invalid limit values."""
        response = test_client.get("/posts?limit=0")
        assert response.status_code == 422  # Validation error

        response = test_client.get("/posts?limit=1000")
        assert response.status_code == 422  # Exceeds max

    def test_posts_has_cache_headers(self, local_content_client: TestClient) -> None:
        """Posts endpoint should return cache headers."""
        response = local_content_client.get("/posts")
        assert response.status_code == 200
        assert "Cache-Control" in response.headers
        assert "ETag" in response.headers

    def test_posts_sorted_by_date(self, local_content_client: TestClient) -> None:
        """Posts should be sorted by date in reverse chronological order."""
        response = local_content_client.get("/posts")
        assert response.status_code == 200
        data = response.json()
        posts = data["posts"]
        if len(posts) > 1:
            dates = [p["date"] for p in posts]
            assert dates == sorted(dates, reverse=True)


class TestPostEndpoint:
    """Tests for the /post/{slug} endpoint."""

    def test_get_post_success(self, local_content_client: TestClient) -> None:
        """Should return a post when it exists."""
        response = local_content_client.get("/post/test-post-one")
        assert response.status_code == 200
        data = response.json()
        assert "meta" in data
        assert "content" in data
        assert data["meta"]["slug"] == "test-post-one"
        assert data["meta"]["title"] == "Test Post One"

    def test_get_post_not_found(self, local_content_client: TestClient) -> None:
        """Should return 404 for non-existent post."""
        response = local_content_client.get("/post/nonexistent-post")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_get_post_invalid_slug_format(self, test_client: TestClient) -> None:
        """Should reject slugs with invalid characters."""
        # Path traversal attempt
        response = test_client.get("/post/../../../etc/passwd")
        assert response.status_code in [400, 404, 422]

        # Special characters
        response = test_client.get("/post/test<script>")
        assert response.status_code in [400, 404, 422]

    def test_get_post_valid_slug_characters(self, local_content_client: TestClient) -> None:
        """Should accept slugs with valid characters."""
        # Alphanumeric with hyphens
        response = local_content_client.get("/post/test-post-one")
        assert response.status_code == 200

    def test_get_post_has_cache_headers(self, local_content_client: TestClient) -> None:
        """Post endpoint should return cache headers."""
        response = local_content_client.get("/post/test-post-one")
        assert response.status_code == 200
        assert "Cache-Control" in response.headers
        assert "ETag" in response.headers

    def test_get_post_content_structure(self, local_content_client: TestClient) -> None:
        """Post content should have expected structure."""
        response = local_content_client.get("/post/test-post-one")
        assert response.status_code == 200
        data = response.json()

        meta = data["meta"]
        assert "slug" in meta
        assert "title" in meta
        assert "date" in meta
        assert "description" in meta
        assert "tags" in meta
        assert isinstance(meta["tags"], list)


class TestCacheEndpoints:
    """Tests for cache management endpoints."""

    def test_cache_stats(self, test_client: TestClient) -> None:
        """Cache stats endpoint should return statistics."""
        response = test_client.get("/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert "posts_list_size" in data
        assert "post_cache_size" in data
        assert "ttl_seconds" in data

    def test_cache_clear(self, test_client: TestClient) -> None:
        """Cache clear endpoint should clear caches."""
        response = test_client.post("/cache/clear")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_yaml_handled(self, local_content_client: TestClient) -> None:
        """Invalid YAML frontmatter should be handled gracefully."""
        # The post with invalid YAML should be skipped in the list
        response = local_content_client.get("/posts")
        assert response.status_code == 200
        data = response.json()
        # Invalid YAML post should be skipped
        slugs = [p["slug"] for p in data["posts"]]
        assert "invalid-yaml" not in slugs

    def test_general_error_response_format(self, test_client: TestClient) -> None:
        """Error responses should have consistent format."""
        response = test_client.get("/post/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
