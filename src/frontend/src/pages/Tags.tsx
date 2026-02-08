import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getPosts } from "../lib/api";
import type { PostSummary } from "../types";

export default function Tags() {
  const [posts, setPosts] = useState<PostSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPosts()
      .then(setPosts)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!posts) return <div className="loading">Loading…</div>;

  // Collect all tags with their post counts
  const tagCounts = new Map<string, number>();
  posts.forEach((post) => {
    post.tags?.forEach((tag) => {
      tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
    });
  });

  // Sort tags alphabetically
  const sortedTags = Array.from(tagCounts.entries()).sort((a, b) =>
    a[0].localeCompare(b[0])
  );

  return (
    <div className="tags-page">
      <h1>Tags</h1>
      <p className="muted">Browse posts by topic</p>
      <div className="tags-grid">
        {sortedTags.map(([tag, count]) => (
          <Link key={tag} to={`/tags/${tag}`} className="tag-card">
            <span className="tag-name">{tag}</span>
            <span className="tag-count">{count} post{count !== 1 ? "s" : ""}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
