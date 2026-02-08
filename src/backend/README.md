# dev-blog Backend

FastAPI service that serves blog metadata and content from S3.

## Requirements

- Python 3.11+
- AWS credentials configured (env vars, AWS profile, or instance role)
- [uv](https://docs.astral.sh/uv/) installed

## Setup (with uv)

```bash
cd backend
uv venv            # create .venv (once)
uv sync            # install deps from pyproject.toml
cp .env.example .env
# Edit .env with your S3 bucket name
```

## Run (dev)

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# or
./dev.sh
```

## Endpoints

- `GET /health`
- `GET /posts` → list of posts (title, date, description, tags, slug)
- `GET /post/{slug}` → post detail with front matter and Markdown content

## Notes

- Posts are read from S3: `s3://$DEV_BLOG_S3_BUCKET/$DEV_BLOG_S3_PREFIX`
- Cache TTL is controlled by `DEV_BLOG_CACHE_TTL_SECONDS`.
