# FRONTEND KNOWLEDGE BASE

React SPA consuming FastAPI backend, built with Vite + TypeScript.

## STRUCTURE

```text
frontend/
├── src/
│   ├── main.tsx        # React entry (StrictMode + BrowserRouter)
│   ├── App.tsx         # Routes + layout + ErrorBoundary
│   ├── pages/          # Route components (Home, Post, About, Tags)
│   ├── components/     # Shared components (ErrorBoundary, Hero, PostList)
│   ├── lib/api.ts      # API client with ETag caching
│   └── types.ts        # TypeScript interfaces (matches backend models)
├── index.html          # HTML entry point
├── vite.config.ts      # Vite config (minimal)
└── tsconfig.json       # TypeScript strict mode
```

## WHERE TO LOOK

| Task | File | Notes |
| ---- | ---- | ----- |
| Add page | `src/pages/` | Register route in `App.tsx` |
| Add component | `src/components/` | Use function components |
| Modify API calls | `src/lib/api.ts` | Follow `getPosts`/`getPost` pattern |
| Add type | `src/types.ts` | Keep in sync with backend models |
| Change routing | `src/App.tsx` | Inside `<Routes>` block |

## CONVENTIONS

### API Client Pattern

```typescript
// api.ts uses client-side caching with ETag support
export async function getPost(slug: string): Promise<PostDetail> {
  // Validates slug client-side before request
  if (!/^[a-zA-Z0-9_-]+$/.test(slug)) {
    throw new Error("Invalid post slug format");
  }
  return fetchWithCache<PostDetail>(`/post/${slug}`);
}
```

### Component Pattern

```typescript
// Function components only, no class components
export default function PageName() {
  // Hooks at top
  const [data, setData] = useState<Type | null>(null);
  // Early returns for loading/error
  if (!data) return <div>Loading...</div>;
  // Render
  return <div>...</div>;
}
```

### Error Handling

- App wrapped in `<ErrorBoundary>` at two levels (root + routes)
- API errors throw, caught by boundary
- Show user-friendly error messages

## ANTI-PATTERNS

| Don't | Do Instead |
| ----- | ---------- |
| `console.log()` | Remove before commit (pre-commit blocks) |
| `any` type | Define proper interface in `types.ts` |
| Class components | Function components with hooks |
| Direct fetch() | Use `api.ts` functions (caching) |

## BUILD & DEV

```bash
# Development
npm run dev          # Vite dev server on :5173

# Build
npm run build        # tsc -b && vite build

# Preview production build
npm run preview

# Lint
npx eslint src/
npx prettier --check .
```

## NOTES

- **No tests**: Test framework not configured (only linting)
- **API URL**: Set via `VITE_API_URL` at build time
- **Double ErrorBoundary**: Intentional defensive pattern
- **Cache TTL**: 5 minutes client-side (`CACHE_TTL` in api.ts)
- **TypeScript strict**: All strict checks enabled
