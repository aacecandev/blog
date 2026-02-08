# BACKEND KNOWLEDGE BASE

FastAPI REST API serving markdown blog posts from S3 or local filesystem.

## STRUCTURE

```text
backend/
├── main.py           # App entry + routes + exception handlers
├── config.py         # Pydantic settings (DEV_BLOG_* prefix)
├── models.py         # Request/response models with slug validation
├── content_store.py  # Storage abstraction (local/S3 switching)
├── cache.py          # TTL cache with stats endpoint
├── s3_client.py      # S3 operations with singleton pattern
├── middleware.py     # Rate limiting + request logging
├── telemetry.py      # Optional OpenTelemetry (lazy-loaded)
└── tests/            # pytest with moto for S3 mocking
```

## WHERE TO LOOK

| Task | File | Function/Class |
| ---- | ---- | -------------- |
| Add endpoint | `main.py` | After existing `@app.get/post` decorators |
| Add model | `models.py` | Follow `PostMeta`/`PostDetail` pattern |
| Add env var | `config.py` | Add to `Settings` class with `DEV_BLOG_` prefix |
| Modify caching | `cache.py` | `get_*_cached()` / `set_*_cached()` functions |
| Change S3 logic | `s3_client.py` | `S3Client` singleton class |
| Add middleware | `main.py` | After line 87 (order matters: outermost first) |

## CONVENTIONS

### Error Handling

```python
# Custom exceptions (content_store.py, s3_client.py)
raise ContentError("message")  # → 503 Service Unavailable
raise S3Error("message")       # → 503 Service Unavailable
# Never use bare except: or catch Exception without re-raising
```

### Validation

```python
# Slug validation pattern (3 layers - keep all 3)
SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")  # main.py
_validate_slug(slug)  # content_store.py
@field_validator("slug")  # models.py
```

### Caching Pattern

```python
# Always check cache first
cached = get_post_cached(slug)
if cached is not None:
    return cached
# Load from storage
result = load_post_by_slug(slug)
set_post_cached(slug, result)
return result
```

## ANTI-PATTERNS

| Don't | Do Instead |
| ----- | ---------- |
| `print()` | `from .config import logger; logger.info()` |
| Bare `except:` | `except (ContentError, S3Error) as e:` |
| `settings.s3_bucket = "x"` | `object.__setattr__(settings, "s3_bucket", "x")` (Pydantic frozen) |
| Skip slug validation | Keep all 3 validation layers |

## TESTING

```bash
# Run tests
pytest -v

# With coverage
pytest --cov=. --cov-report=term-missing

# Single test class
pytest tests/test_main.py::TestPostsEndpoint -v
```

### Test Patterns

- **Fixtures**: `conftest.py` sets env vars BEFORE imports
- **Cache isolation**: `clear_all_caches()` in test_client fixture
- **S3 mocking**: `@mock_s3` decorator + moto library
- **Settings override**: `object.__setattr__(settings, "key", "value")`

## NOTES

- **Middleware order**: RequestLogging added last but runs first (ASGI reversal)
- **Rate limiting**: Disabled when `DEV_BLOG_ENVIRONMENT=local`
- **Cache TTL**: Set via `DEV_BLOG_CACHE_TTL_SECONDS` (0 = disabled)
- **S3 client**: Singleton pattern, cached slug→key mapping
