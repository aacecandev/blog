"""Application configuration using pydantic-settings.

This module provides centralized configuration management with support for
environment variables and .env files. All settings use the DEV_BLOG_ prefix.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All environment variables should be prefixed with DEV_BLOG_.
    Example: DEV_BLOG_S3_BUCKET=my-bucket

    Attributes:
        app_name: Name of the application for logging/metadata.
        environment: Deployment environment (local, dev, staging, prod).
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        aws_region: AWS region for S3 operations.
        s3_bucket: S3 bucket name for blog content storage.
        s3_prefix: Prefix/folder path within the S3 bucket.
        content_dir: Local directory for development (bypasses S3 if set).
        cache_ttl_seconds: TTL for cached content in seconds.
        cors_origins: List of allowed CORS origins.
    """

    app_name: str = Field(default="dev-blog-backend")
    environment: Literal["local", "dev", "staging", "prod"] = Field(default="local")
    log_level: str = Field(default="INFO")

    # AWS/S3 Configuration
    aws_region: str = Field(default="eu-west-1")
    s3_bucket: str = Field(default="")
    s3_prefix: str = Field(default="posts/")

    # Local development: if set, read Markdown from this directory instead of S3
    content_dir: str = Field(default="")

    # Caching
    cache_ttl_seconds: int = Field(default=300, ge=0, le=86400)

    # CORS - environment-aware defaults
    # Production should set DEV_BLOG_CORS_ORIGINS to specific domains
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins. Set to specific domains in production."
    )

    @property
    def effective_cors_origins(self) -> list[str]:
        """Get CORS origins with production safety check.

        In production, if cors_origins contains '*', log a warning.
        """
        if self.is_production and "*" in self.cors_origins:
            import logging
            logging.getLogger("dev-blog").warning(
                "SECURITY WARNING: CORS allows all origins ('*') in production. "
                "Set DEV_BLOG_CORS_ORIGINS to specific domains."
            )
        return self.cors_origins

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = "DEV_BLOG_"

    @property
    def is_using_s3(self) -> bool:
        """Check if S3 storage is configured."""
        return bool(self.s3_bucket) and not self.content_dir

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "prod"


def setup_logging(settings: Settings) -> logging.Logger:
    """Configure application logging.

    Args:
        settings: Application settings containing log level.

    Returns:
        Configured logger instance for the application.
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    if settings.environment == "local":
        # More detailed format for local development
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=log_format,
    )

    logger = logging.getLogger("dev-blog")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    return logger


# Global settings instance
settings = Settings()

# Global logger instance
logger = setup_logging(settings)
