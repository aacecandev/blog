import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { getPost } from "../lib/api";
import type { PostDetail } from "../types";

export default function Post() {
  const { slug } = useParams<{ slug: string }>();
  const [post, setPost] = useState<PostDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    getPost(slug)
      .then(setPost)
      .catch((e) => setError(String(e)));
  }, [slug]);

  if (error) return <div className="error">{error}</div>;
  if (!post) return <div className="loading">Loading…</div>;

  return (
    <article className="post">
      <h1>{post.meta.title}</h1>
      {post.meta.date && <p className="muted">{post.meta.date}</p>}
      {post.meta.description && <p>{post.meta.description}</p>}
      {!!post.meta.tags?.length && (
        <div className="tags">
          {post.meta.tags.map((t) => (
            <span key={t} className="tag">
              {t}
            </span>
          ))}
        </div>
      )}
      <hr />
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {post.content}
      </ReactMarkdown>
    </article>
  );
}
