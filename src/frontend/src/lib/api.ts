import type { PostSummary, PostDetail, PostListResponse } from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Cache for API responses with TTL
 */
interface CacheEntry<T> {
  data: T;
  timestamp: number;
  etag?: string;
}

const cache = new Map<string, CacheEntry<unknown>>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Fetch with caching and ETag support
 */
async function fetchWithCache<T>(url: string): Promise<T> {
  const cacheKey = url;
  const cached = cache.get(cacheKey) as CacheEntry<T> | undefined;

  const headers: HeadersInit = {};

  // Use ETag for conditional requests if we have a cached response
  if (cached?.etag) {
    headers["If-None-Match"] = cached.etag;
  }

  const res = await fetch(`${API_BASE}${url}`, { headers });

  // Return cached data if not modified
  if (res.status === 304 && cached) {
    return cached.data;
  }

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  const data = await res.json();
  const etag = res.headers.get("ETag") || undefined;

  // Update cache
  cache.set(cacheKey, {
    data,
    timestamp: Date.now(),
    etag,
  });

  return data;
}

/**
 * Check if cached data is still fresh
 */
function getCachedData<T>(url: string): T | null {
  const cached = cache.get(url) as CacheEntry<T> | undefined;
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }
  return null;
}

/**
 * Fetch all posts with pagination support
 */
export async function getPosts(
  limit = 20,
  offset = 0
): Promise<PostSummary[]> {
  const url = `/posts?limit=${limit}&offset=${offset}`;

  // Check cache first
  const cached = getCachedData<PostListResponse>(url);
  if (cached) {
    return cached.posts;
  }

  const response = await fetchWithCache<PostListResponse>(url);
  return response.posts;
}

/**
 * Fetch all posts with full response (includes pagination metadata)
 */
export async function getPostsWithPagination(
  limit = 20,
  offset = 0
): Promise<PostListResponse> {
  const url = `/posts?limit=${limit}&offset=${offset}`;
  return fetchWithCache<PostListResponse>(url);
}

/**
 * Fetch a single post by slug
 */
export async function getPost(slug: string): Promise<PostDetail> {
  // Validate slug format on client side to avoid unnecessary requests
  if (!/^[a-zA-Z0-9_-]+$/.test(slug)) {
    throw new Error("Invalid post slug format");
  }

  const url = `/post/${encodeURIComponent(slug)}`;
  return fetchWithCache<PostDetail>(url);
}

/**
 * Clear all cached data
 */
export function clearCache(): void {
  cache.clear();
}

/**
 * Invalidate cache for a specific URL pattern
 */
export function invalidateCache(pattern: string): void {
  for (const key of cache.keys()) {
    if (key.includes(pattern)) {
      cache.delete(key);
    }
  }
}
