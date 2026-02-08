"""Middleware components for the FastAPI application.

This module provides rate limiting and request logging middleware.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .config import logger, settings


# =============================================================================
# Rate Limiting
# =============================================================================


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""

    requests: list[float] = field(default_factory=list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using sliding window algorithm.

    Limits requests per IP address to prevent abuse.
    Uses in-memory storage (suitable for single-instance deployments).

    For distributed deployments, consider using Redis-based rate limiting.
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.enabled = enabled
        self.buckets: dict[str, RateLimitBucket] = defaultdict(RateLimitBucket)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        # Check X-Forwarded-For header (set by reverse proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection IP
        if request.client:
            return request.client.host

        return "unknown"

    def _is_rate_limited(self, client_ip: str) -> tuple[bool, dict[str, str]]:
        """Check if client is rate limited.

        Returns:
            Tuple of (is_limited, headers_dict with rate limit info)
        """
        now = time.time()
        bucket = self.buckets[client_ip]

        # Clean old requests (older than 1 hour)
        bucket.requests = [t for t in bucket.requests if now - t < 3600]

        # Count requests in time windows
        minute_ago = now - 60
        requests_last_minute = sum(1 for t in bucket.requests if t > minute_ago)
        requests_last_hour = len(bucket.requests)

        # Calculate remaining
        remaining_minute = max(0, self.requests_per_minute - requests_last_minute)
        remaining_hour = max(0, self.requests_per_hour - requests_last_hour)

        headers = {
            "X-RateLimit-Limit-Minute": str(self.requests_per_minute),
            "X-RateLimit-Remaining-Minute": str(remaining_minute),
            "X-RateLimit-Limit-Hour": str(self.requests_per_hour),
            "X-RateLimit-Remaining-Hour": str(remaining_hour),
        }

        # Check if over limit
        if requests_last_minute >= self.requests_per_minute:
            headers["Retry-After"] = "60"
            return True, headers

        if requests_last_hour >= self.requests_per_hour:
            headers["Retry-After"] = "3600"
            return True, headers

        return False, headers

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting if disabled or for health checks
        if not self.enabled or request.url.path == "/health":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        is_limited, headers = self._is_rate_limited(client_ip)

        if is_limited:
            logger.warning("Rate limit exceeded for IP: %s", client_ip)
            response = Response(
                content='{"detail":"Rate limit exceeded. Please try again later."}',
                status_code=429,
                media_type="application/json",
            )
            for key, value in headers.items():
                response.headers[key] = value
            return response

        # Record this request
        self.buckets[client_ip].requests.append(time.time())

        # Process request and add rate limit headers to response
        response = await call_next(request)
        for key, value in headers.items():
            response.headers[key] = value

        return response


# =============================================================================
# Request Logging
# =============================================================================


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request logging.

    Logs request method, path, status code, and response time.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        start_time = time.time()

        # Get client IP
        client_ip = request.headers.get(
            "X-Forwarded-For",
            request.headers.get("X-Real-IP", request.client.host if request.client else "unknown"),
        )
        if "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()

        # Process request
        response = await call_next(request)

        # Calculate response time
        process_time = (time.time() - start_time) * 1000  # ms

        # Log request details (skip health checks in production)
        if settings.environment != "prod" or request.url.path != "/health":
            logger.info(
                "Request: %s %s - Status: %d - Time: %.2fms - IP: %s",
                request.method,
                request.url.path,
                response.status_code,
                process_time,
                client_ip,
            )

        # Add timing header
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

        return response
