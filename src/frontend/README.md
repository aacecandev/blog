# dev-blog Frontend (React + Vite)

Minimal SPA that consumes the FastAPI backend and renders Markdown posts.

## Setup

```bash
cd frontend
npm install
# or: pnpm i / bun i
```

## Env

Create a `.env` with:

```
VITE_API_URL=http://localhost:8000
```

## Run

```bash
npm run dev
```

## Build

```bash
npm run build && npm run preview
```
