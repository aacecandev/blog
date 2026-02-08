import { Routes, Route, Link } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import Home from "./pages/Home";
import Post from "./pages/Post";
import About from "./pages/About";
import Tags from "./pages/Tags";

export default function App() {
  return (
    <ErrorBoundary>
      <div className="layout">
        <header className="site-header">
          <div className="header-content">
            <Link to="/" className="brand">
              dev.aacecan.com
            </Link>
            <nav className="nav" aria-label="Main navigation">
              <Link to="/tags" className="nav-link">Tags</Link>
              <Link to="/about" className="nav-link">About</Link>
            </nav>
          </div>
        </header>
        <div className="container">
          <main role="main" aria-live="polite">
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/post/:slug" element={<Post />} />
                <Route path="/about" element={<About />} />
                <Route path="/tags" element={<Tags />} />
                <Route path="/tags/:tag" element={<Home />} />
              </Routes>
            </ErrorBoundary>
          </main>
          <footer className="site-footer" role="contentinfo">
            <span>© {new Date().getFullYear()} dev.aacecan.com</span>
          </footer>
        </div>
      </div>
    </ErrorBoundary>
  );
}
