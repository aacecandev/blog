"""Caching utilities for blog content.

This module provides in-memory TTL-based caching for posts and metadata
to reduce S3/filesystem reads and improve response times.
"""

from __future__ import annotations

from typing import Any

from cachetools import TTLCache

from .config import logger, settings

# Cache size constants
MAX_INDIVIDUAL_POST_CACHE = 512  # Max number of individual posts to cache
POSTS_LIST_CACHE_SIZE = 1  # Single entry for the full posts list
SLUG_MAP_CACHE_SIZE = 1  # Single entry for slug-to-key mapping

# Cache instances with configurable TTL
_posts_list_cache: TTLCache[str, Any] = TTLCache(
    maxsize=POSTS_LIST_CACHE_SIZE, ttl=settings.cache_ttl_seconds
)
_post_cache: TTLCache[str, Any] = TTLCache(
    maxsize=MAX_INDIVIDUAL_POST_CACHE, ttl=settings.cache_ttl_seconds
)
_slug_map_cache: TTLCache[str, dict[str, str]] = TTLCache(
    maxsize=SLUG_MAP_CACHE_SIZE, ttl=settings.cache_ttl_seconds
)


def get_posts_list_cached() -> Any | None:
    """Get cached list of post summaries.

    Returns:
        Cached list of PostSummary objects, or None if not cached.
    """
    result = _posts_list_cache.get("posts_list")
    if result is not None:
        logger.debug("Cache hit for posts list")
    return result


def set_posts_list_cached(value: Any) -> None:
    """Cache the list of post summaries.

    Args:
        value: List of PostSummary objects to cache.
    """
    _posts_list_cache["posts_list"] = value
    logger.debug("Cached posts list with %d items", len(value) if value else 0)


def get_post_cached(slug: str) -> Any | None:
    """Get a cached individual post by slug.

    Args:
        slug: The post's URL slug identifier.

    Returns:
        Cached PostDetail object, or None if not cached.
    """
    result = _post_cache.get(slug)
    if result is not None:
        logger.debug("Cache hit for post: %s", slug)
    return result


def set_post_cached(slug: str, value: Any) -> None:
    """Cache an individual post.

    Args:
        slug: The post's URL slug identifier.
        value: PostDetail object to cache.
    """
    _post_cache[slug] = value
    logger.debug("Cached post: %s", slug)


def get_slug_map_cached() -> dict[str, str] | None:
    """Get cached slug-to-S3-key mapping.

    Returns:
        Dictionary mapping slugs to S3 keys, or None if not cached.
    """
    result = _slug_map_cache.get("slug_map")
    if result is not None:
        logger.debug("Cache hit for slug map")
    return result


def set_slug_map_cached(value: dict[str, str]) -> None:
    """Cache the slug-to-S3-key mapping.

    Args:
        value: Dictionary mapping slugs to their S3 keys.
    """
    _slug_map_cache["slug_map"] = value
    logger.debug("Cached slug map with %d entries", len(value))


def clear_all_caches() -> None:
    """Clear all caches. Useful for testing or forced refresh."""
    _posts_list_cache.clear()
    _post_cache.clear()
    _slug_map_cache.clear()
    logger.info("All caches cleared")


def get_cache_stats() -> dict[str, Any]:
    """Get current cache statistics.

    Returns:
        Dictionary with cache hit/size information.
    """
    return {
        "posts_list_size": len(_posts_list_cache),
        "post_cache_size": len(_post_cache),
        "post_cache_max": MAX_INDIVIDUAL_POST_CACHE,
        "slug_map_size": len(_slug_map_cache),
        "ttl_seconds": settings.cache_ttl_seconds,
    }
