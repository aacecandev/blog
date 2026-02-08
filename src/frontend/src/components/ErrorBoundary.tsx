import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error boundary component that catches JavaScript errors anywhere in the
 * child component tree, logs those errors, and displays a fallback UI.
 *
 * Usage:
 * ```tsx
 * <ErrorBoundary>
 *   <MyComponent />
 * </ErrorBoundary>
 * ```
 *
 * With custom fallback:
 * ```tsx
 * <ErrorBoundary fallback={<div>Something went wrong</div>}>
 *   <MyComponent />
 * </ErrorBoundary>
 * ```
 */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error to console in development
    console.error("ErrorBoundary caught an error:", error, errorInfo);

    // In production, you could send to an error tracking service like Sentry
    // if (import.meta.env.PROD) {
    //   sendToErrorTracking(error, errorInfo);
    // }
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Custom fallback
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default fallback UI
      return (
        <div className="error-boundary">
          <div className="error-boundary-content">
            <h2>Something went wrong</h2>
            <p className="muted">
              An unexpected error occurred. Please try refreshing the page.
            </p>
            {import.meta.env.DEV && this.state.error && (
              <details className="error-details">
                <summary>Error details (dev only)</summary>
                <pre>{this.state.error.message}</pre>
                <pre>{this.state.error.stack}</pre>
              </details>
            )}
            <div className="error-actions">
              <button className="btn" onClick={this.handleRetry}>
                Try Again
              </button>
              <button
                className="btn btn-outline"
                onClick={() => window.location.reload()}
              >
                Refresh Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
