"""FastAPI application for the dev blog backend.

This module provides REST API endpoints for serving blog posts stored
in S3 or local filesystem, with caching, pagination, and proper error handling.
"""

from __future__ import annotations

import hashlib
import re
from typing import Annotated

import frontmatter
import yaml
from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .cache import (
    clear_all_caches,
    get_cache_stats,
    get_post_cached,
    get_posts_list_cached,
    set_post_cached,
    set_posts_list_cached,
)
from .config import logger, settings
from .middleware import RateLimitMiddleware, RequestLoggingMiddleware
from .telemetry import init_telemetry, instrument_fastapi
from .content_store import ContentError, list_post_slugs, load_post_by_slug
from .models import (
    ErrorResponse,
    HealthResponse,
    PostDetail,
    PostListResponse,
    PostMeta,
    PostSummary,
)
from .s3_client import S3Error

# Slug validation pattern for path parameter
SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# Pagination defaults
DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100

# Minimum response size for gzip compression (bytes)
GZIP_MINIMUM_SIZE = 500

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="REST API for serving blog posts from S3 or local storage",
    version="0.1.0",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

# Initialize OpenTelemetry tracing (if enabled)
init_telemetry(settings.app_name)
instrument_fastapi(app)

# Add request logging middleware (outermost - runs first/last)
app.add_middleware(RequestLoggingMiddleware)

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=60,
    requests_per_hour=1000,
    enabled=settings.environment != "local",  # Disable in local dev
)

# Add Gzip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=GZIP_MINIMUM_SIZE)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.effective_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Exception Handlers
# =============================================================================


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle validation errors with 400 Bad Request."""
    logger.warning("Validation error on %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "error_code": "VALIDATION_ERROR"},
    )


@app.exception_handler(ContentError)
async def content_error_handler(request: Request, exc: ContentError) -> JSONResponse:
    """Handle content storage errors with 503 Service Unavailable."""
    logger.error("Content error on %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=503,
        content={"detail": "Content temporarily unavailable", "error_code": "CONTENT_ERROR"},
    )


@app.exception_handler(S3Error)
async def s3_error_handler(request: Request, exc: S3Error) -> JSONResponse:
    """Handle S3 errors with 503 Service Unavailable."""
    logger.error("S3 error on %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=503,
        content={"detail": "Storage service temporarily unavailable", "error_code": "S3_ERROR"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors with 500 Internal Server Error."""
    logger.exception("Unhandled error on %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"},
    )


# =============================================================================
# Lifecycle Events
# =============================================================================


@app.on_event("startup")
async def startup_event() -> None:
    """Log startup information."""
    logger.info(
        "Starting %s (env=%s, s3=%s, cache_ttl=%ds)",
        settings.app_name,
        settings.environment,
        settings.is_using_s3,
        settings.cache_ttl_seconds,
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Log shutdown."""
    logger.info("Shutting down %s", settings.app_name)


# =============================================================================
# Helper Functions
# =============================================================================


def generate_etag(content: str) -> str:
    """Generate ETag hash from content.

    Args:
        content: String content to hash.

    Returns:
        ETag string with quotes.
    """
    return f'"{hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()}"'


def add_cache_headers(response: JSONResponse, etag: str | None = None) -> JSONResponse:
    """Add HTTP caching headers to response.

    Args:
        response: JSONResponse to modify.
        etag: Optional ETag value.

    Returns:
        Response with caching headers.
    """
    response.headers["Cache-Control"] = f"public, max-age={settings.cache_ttl_seconds}"
    if etag:
        response.headers["ETag"] = etag
    return response


def parse_frontmatter(raw: str, slug: str) -> tuple[dict, str]:
    """Parse frontmatter from raw Markdown content.

    Args:
        raw: Raw Markdown content with YAML frontmatter.
        slug: Post slug for error reporting.

    Returns:
        Tuple of (metadata dict, content string).

    Raises:
        ValueError: If frontmatter parsing fails.
    """
    try:
        parsed = frontmatter.loads(raw)
        return parsed.metadata or {}, parsed.content
    except yaml.YAMLError as e:
        logger.error("YAML parse error in post %s: %s", slug, str(e))
        raise ValueError(f"Invalid frontmatter format in post: {slug}") from e


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Service information endpoint.

    Returns:
        Service metadata and available endpoints.
    """
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "endpoints": ["/health", "/posts", "/post/{slug}", "/docs"],
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health() -> HealthResponse:
    """Health check endpoint.

    Returns:
        Service health status.
    """
    return HealthResponse(status="ok")


@app.get("/cache/stats", tags=["System"], include_in_schema=False)
async def cache_stats() -> dict:
    """Get cache statistics (internal endpoint).

    Returns:
        Current cache sizes and configuration.
    """
    return get_cache_stats()


@app.post("/cache/clear", tags=["System"], include_in_schema=False)
async def cache_clear() -> dict:
    """Clear all caches (internal endpoint).

    Returns:
        Confirmation message.
    """
    clear_all_caches()
    return {"message": "All caches cleared"}


@app.get("/posts", response_model=PostListResponse, tags=["Posts"])
async def list_posts(
    limit: Annotated[
        int, Query(ge=1, le=MAX_PAGE_LIMIT, description="Max posts per page")
    ] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0, description="Number of posts to skip")] = 0,
) -> JSONResponse:
    """List blog posts with pagination.

    Args:
        limit: Maximum number of posts to return (1-100, default 20).
        offset: Number of posts to skip for pagination.

    Returns:
        Paginated list of post summaries with metadata.
    """
    # Try to get from cache first
    all_summaries = get_posts_list_cached()

    if all_summaries is None:
        logger.debug("Cache miss for posts list, loading from storage")
        slugs = list_post_slugs()
        all_summaries: list[PostSummary] = []

        for slug in slugs:
            try:
                raw = load_post_by_slug(slug)
                meta_dict, _ = parse_frontmatter(raw, slug)
                all_summaries.append(
                    PostSummary(
                        slug=slug,
                        title=str(meta_dict.get("title", slug)),
                        date=str(meta_dict.get("date", "")),
                        description=meta_dict.get("description"),
                        tags=list(meta_dict.get("tags", []) or []),
                    )
                )
            except (ValueError, FileNotFoundError) as e:
                logger.warning("Skipping post %s due to error: %s", slug, str(e))
                continue

        # Sort reverse chronological by date string
        all_summaries.sort(key=lambda s: s.date, reverse=True)
        set_posts_list_cached(all_summaries)

    # Apply pagination
    total = len(all_summaries)
    paginated = all_summaries[offset : offset + limit]

    # Build response with caching headers
    response_data = PostListResponse(
        posts=paginated,
        total=total,
        limit=limit,
        offset=offset,
    )

    response = JSONResponse(content=response_data.model_dump())
    etag = generate_etag(f"{total}-{offset}-{limit}")
    return add_cache_headers(response, etag)


@app.get(
    "/post/{slug}",
    response_model=PostDetail,
    responses={
        404: {"model": ErrorResponse, "description": "Post not found"},
        400: {"model": ErrorResponse, "description": "Invalid slug format"},
    },
    tags=["Posts"],
)
async def get_post(
    slug: Annotated[
        str, Path(pattern=r"^[a-zA-Z0-9_-]+$", max_length=200, description="Post URL slug")
    ],
) -> JSONResponse:
    """Get a single blog post by slug.

    Args:
        slug: URL-safe identifier for the post.

    Returns:
        Full post content with metadata.

    Raises:
        HTTPException: 404 if post not found, 400 if invalid slug.
    """
    # Validate slug format (redundant with Path validation, but explicit)
    if not SLUG_PATTERN.match(slug):
        logger.warning("Invalid slug format requested: %s", slug)
        raise HTTPException(
            status_code=400,
            detail="Invalid slug format. Use only alphanumeric characters, hyphens, and underscores.",
        )

    # Check cache first
    cached = get_post_cached(slug)
    if cached is not None:
        response = JSONResponse(content=cached.model_dump())
        etag = generate_etag(cached.content)
        return add_cache_headers(response, etag)

    # Load from storage
    try:
        raw = load_post_by_slug(slug)
    except FileNotFoundError:
        logger.debug("Post not found: %s", slug)
        raise HTTPException(status_code=404, detail="Post not found") from None

    # Parse frontmatter
    meta_dict, content = parse_frontmatter(raw, slug)

    meta = PostMeta(
        slug=slug,
        title=str(meta_dict.get("title", slug)),
        date=str(meta_dict.get("date", "")),
        description=meta_dict.get("description"),
        tags=list(meta_dict.get("tags", []) or []),
    )

    detail = PostDetail(meta=meta, content=content)
    set_post_cached(slug, detail)

    # Return with caching headers
    response = JSONResponse(content=detail.model_dump())
    etag = generate_etag(content)
    return add_cache_headers(response, etag)
