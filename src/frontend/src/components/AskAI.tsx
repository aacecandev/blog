import { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function AskAI() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const responseRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const location = useLocation();

  useEffect(() => {
    if (expanded && inputRef.current) {
      inputRef.current.focus();
    }
  }, [expanded]);

  useEffect(() => {
    if (response && responseRef.current) {
      responseRef.current.scrollTop = responseRef.current.scrollHeight;
    }
  }, [response]);

  // Extract slug from /post/:slug URL
  const slug = location.pathname.match(/^\/post\/([a-zA-Z0-9_-]+)/)?.[1] ?? null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    // Cancel any in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setExpanded(true);
    setResponse("");
    setError("");

    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query, slug }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        setError(`Server error: ${res.status}`);
        setLoading(false);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last (possibly incomplete) line in the buffer
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const chunk = JSON.parse(line);
            if (chunk.token) {
              setResponse((prev) => prev + chunk.token);
            }
            if (chunk.error) {
              setError(chunk.error);
            }
          } catch {
            // skip malformed lines
          }
        }
      }

      // Process any remaining buffer
      if (buffer.trim()) {
        try {
          const chunk = JSON.parse(buffer);
          if (chunk.token) {
            setResponse((prev) => prev + chunk.token);
          }
          if (chunk.error) {
            setError(chunk.error);
          }
        } catch {
          // skip
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError("Failed to connect to AI service.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    abortRef.current?.abort();
    setExpanded(false);
    setResponse("");
    setQuery("");
    setError("");
  };

  return (
    <div className={`ask-ai ${expanded ? "ask-ai--expanded" : ""}`}>
      {expanded && (response || error) && (
        <div className="ask-ai__response" ref={responseRef}>
          <button
            className="ask-ai__close"
            onClick={handleClose}
            aria-label="Close response"
          >
            &times;
          </button>
          <div className="ask-ai__response-text">
            {response}
            {loading && <span className="ask-ai__cursor">|</span>}
          </div>
          {error && <div className="ask-ai__error">{error}</div>}
        </div>
      )}
      <form className="ask-ai__bar" onSubmit={handleSubmit}>
        <div className="ask-ai__input-row">
          <input
            ref={inputRef}
            type="text"
            className="ask-ai__input"
            placeholder="Ask AI about this blog..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            className="ask-ai__submit"
            disabled={!query.trim() || loading}
            aria-label="Send question"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="square"
              strokeLinejoin="miter"
            >
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
}
