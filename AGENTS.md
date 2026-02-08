# AGENTS.md — Dev Blog

Personal dev blog: FastAPI backend serving markdown posts from S3/local, React+Vite frontend.

## Project Layout

```
apps/blog/
├── src/backend/          # FastAPI REST API (Python 3.11+)
│   ├── main.py           # App entry, routes, exception handlers
│   ├── config.py         # Pydantic settings (DEV_BLOG_* env prefix)
│   ├── models.py         # Request/response Pydantic models
│   ├── content_store.py  # Storage abstraction (local/S3)
│   ├── cache.py          # TTL cache with stats endpoint
│   ├── s3_client.py      # S3 singleton client
│   ├── middleware.py      # Rate limiting + request logging
│   ├── telemetry.py      # Optional OpenTelemetry
│   └── tests/            # pytest + moto (S3 mocking)
├── src/frontend/         # React SPA (Vite + TypeScript)
│   └── src/
│       ├── App.tsx        # Routes + layout + ErrorBoundary
│       ├── pages/         # Route components (Home, Post, About, Tags)
│       ├── components/    # Shared (ErrorBoundary, Hero, PostList)
│       ├── lib/api.ts     # API client with ETag caching
│       └── types.ts       # TS interfaces (mirrors backend models)
├── content/posts/        # Markdown blog posts (mounted into container)
└── docker-compose.yml    # api (port 8000) + web (port 8080)
```

## Build / Lint / Test Commands

### Backend (run from `src/backend/`)

```bash
# Run all tests
pytest -v

# Single test file
pytest tests/test_main.py -v

# Single test class or function
pytest tests/test_main.py::TestPostsEndpoint -v
pytest tests/test_main.py::TestPostsEndpoint::test_list_posts -v

# With coverage
pytest --cov=. --cov-report=term-missing

# Lint
ruff check .
ruff format --check .

# Type check
mypy .

# Dev server
uvicorn backend.main:app --reload --port 8000
```

### Frontend (run from `src/frontend/`)

```bash
# Dev server
yarn dev                   # Vite on :5173

# Build (type-check then bundle)
yarn build                 # tsc -b && vite build

# Lint
npx eslint src/
npx prettier --check .

# No test framework configured — lint only
```

### Docker (run from project root)

```bash
docker compose up --build     # api:8000 + web:8080
docker compose up api         # backend only
```

## Code Style — Backend (Python)

### Formatting & Linting

- **Ruff** — line length 100, target Python 3.11
- Rules: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `B` (bugbear), `UP` (pyupgrade)
- Quote style: double quotes, space indent
- **mypy** — `disallow_untyped_defs`, `check_untyped_defs`, strict

### Imports

```python
from __future__ import annotations        # Always first

import hashlib                             # stdlib
import re

import frontmatter                         # third-party
from fastapi import FastAPI, HTTPException

from .config import logger, settings       # relative project imports
from .models import PostDetail, PostMeta
```

Order: `__future__` > stdlib > third-party > relative. Isort enforced by Ruff.

### Naming

- Files: `snake_case.py`
- Classes: `PascalCase` (e.g. `PostMeta`, `S3Client`, `Settings`)
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE` (e.g. `SLUG_PATTERN`, `DEFAULT_PAGE_LIMIT`)
- Env vars: `DEV_BLOG_` prefix (e.g. `DEV_BLOG_S3_BUCKET`)

### Types

- All functions must have full type annotations (mypy `disallow_untyped_defs`)
- Use `str | None` over `Optional[str]` (pyupgrade)
- Use `list[str]` over `List[str]`
- Use `Annotated[str, ...]` for FastAPI param validation

### Error Handling

```python
# Custom exceptions → 503
raise ContentError("message")
raise S3Error("message")

# Never bare except:. Always specify exception types.
except (ContentError, S3Error) as e:

# Logging: never print()
from .config import logger
logger.info("message %s", value)
```

### Docstrings

Google-style with Args/Returns/Raises sections:

```python
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
```

### Key Patterns

- **Settings**: Pydantic `BaseSettings` with `DEV_BLOG_` prefix. Frozen — override with `object.__setattr__(settings, "key", "val")`
- **Caching**: check `get_*_cached()` → miss → load → `set_*_cached()`
- **Slug validation**: 3 layers (Path regex, `_validate_slug()`, `@field_validator`) — keep all 3
- **Middleware order**: added in reverse (outermost = added last, runs first)

### Testing Patterns

- **conftest.py** sets env vars BEFORE importing app modules
- Cache isolation: `clear_all_caches()` in fixture setup/teardown
- S3 mocking: `@mock_s3` decorator + moto, create bucket in fixture
- Settings override: `object.__setattr__(settings, "key", "value")`
- async mode: `asyncio_mode = "auto"` in pyproject.toml

## Code Style — Frontend (TypeScript/React)

### Formatting & Linting

- **Prettier** — double quotes, semicolons, trailing commas, line width 100
- **ESLint** — `@typescript-eslint/recommended` + `react-hooks` plugin
- Unused vars: warn (args prefixed `_` ignored)
- **TypeScript** — strict mode, target ES2020, `react-jsx` transform

### Imports

```typescript
import { Routes, Route, Link } from "react-router-dom";    // third-party
import ErrorBoundary from "./components/ErrorBoundary";     // components
import type { PostSummary } from "../types";                // use `import type` for types
```

### Naming

- Files: `PascalCase.tsx` for components/pages, `camelCase.ts` for utilities
- Components: `PascalCase` function components (no classes)
- Variables/functions: `camelCase`
- Interfaces: `PascalCase` (e.g. `PostSummary`, `PostDetail`)
- Constants: `UPPER_SNAKE_CASE` (e.g. `CACHE_TTL`, `API_BASE`)

### Component Pattern

```typescript
export default function PageName() {
  const [data, setData] = useState<Type | null>(null);
  // hooks at top, early returns for loading/error
  if (!data) return <div>Loading...</div>;
  return <div>...</div>;
}
```

### Anti-Patterns

- No `any` — define interfaces in `types.ts`
- No `console.log()` — remove before commit
- No class components — function components + hooks only
- No direct `fetch()` — use `api.ts` functions (caching + ETag support)
- Types in `types.ts` must stay in sync with backend `models.py`

### Package Manager

Yarn (v1-compatible with `.yarnrc.yml`). Use `yarn add` / `yarn dev` / `yarn build`.
