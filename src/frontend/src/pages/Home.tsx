import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getPosts } from "../lib/api";
import type { PostSummary } from "../types";
import PostList from "../components/PostList";
import Hero from "../components/Hero";

export default function Home() {
  const { tag } = useParams<{ tag?: string }>();
  const [posts, setPosts] = useState<PostSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    getPosts()
      .then(setPosts)
      .catch((e) => setError(String(e)));
  }, []);

  const normalizedQuery = query.trim().toLowerCase();

  const filteredPosts = useMemo(() => {
    let list = posts ?? [];

    // Filter by tag if present in URL
    if (tag) {
      list = list.filter((post) => post.tags?.includes(tag));
    }

    // Filter by search query
    if (normalizedQuery) {
      list = list.filter((post) => {
        const haystack = [post.title, post.description ?? "", ...(post.tags ?? [])]
          .join(" ")
          .toLowerCase();
        return haystack.includes(normalizedQuery);
      });
    }

    return list;
  }, [posts, tag, normalizedQuery]);

  const hasQuery = normalizedQuery.length > 0;

  if (error) return <div className="error">{error}</div>;
  if (!posts) return <div className="loading">Loading…</div>;

  return (
    <>
      {!tag && <Hero />}

      {tag && (
        <div className="tag-filter-header">
          <h1>
            Posts tagged: <span className="tag">{tag}</span>
          </h1>
          <Link to="/" className="btn btn-outline">← All posts</Link>
        </div>
      )}

      <div className="search">
        <label htmlFor="post-search" className="visually-hidden">
          Search posts
        </label>
        <input
          id="post-search"
          type="search"
          placeholder="Search posts…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        {(hasQuery || tag) && (
          <p className="muted small">
            Showing {filteredPosts.length} of {posts.length} post{posts.length === 1 ? "" : "s"}
          </p>
        )}
      </div>

      <PostList
        posts={filteredPosts}
        emptyMessage={hasQuery ? "No posts match your search." : tag ? `No posts tagged "${tag}".` : undefined}
      />
    </>
  );
}
