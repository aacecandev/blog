import { Link } from "react-router-dom";
import type { PostSummary } from "../types";

type PostListProps = {
  posts: PostSummary[];
  emptyMessage?: string;
};

export default function PostList({ posts, emptyMessage = "No posts yet." }: PostListProps) {
  if (!posts.length) return <div>{emptyMessage}</div>;
  return (
    <div className="grid">
      {posts.map((p) => (
        <Link key={p.slug} to={`/post/${p.slug}`} className="card">
          <h3>{p.title}</h3>
          {p.date && <p className="muted small">{p.date}</p>}
          {p.description && <p>{p.description}</p>}
          {!!p.tags?.length && (
            <div className="tags">
              {p.tags.map((t) => (
                <span key={t} className="tag">
                  {t}
                </span>
              ))}
            </div>
          )}
        </Link>
      ))}
    </div>
  );
}
