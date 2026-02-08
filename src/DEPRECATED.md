# DEPRECATED

This directory (`src/`) contains the **legacy** FastAPI backend implementation with Jinja2 templates.

## Current Status

This code is **no longer actively maintained**. The active backend is located at:

```
app/backend/
```

## Why This Exists

This was the original implementation of the blog backend that served HTML templates directly. The project has since migrated to a decoupled architecture:

- **Frontend**: React + TypeScript (see `app/frontend/`)
- **Backend**: FastAPI REST API (see `app/backend/`)

## Do NOT Use

- Do not add new features to this directory
- Do not fix bugs here unless critical
- New development should go to `app/backend/` and `app/frontend/`

## Removal Timeline

This directory will be removed in a future release once we confirm no dependencies remain.

## Migration Notes

If you were using the old endpoints:
- `GET /` (HTML) → Use React frontend at `app/frontend/`
- `GET /post/{slug}` (HTML) → `GET /post/{slug}` (JSON) from `app/backend/`
- `GET /tag/{tag}` (HTML) → Filter by tag in React frontend
- `GET /category/{category}` (HTML) → Not currently supported in new API
