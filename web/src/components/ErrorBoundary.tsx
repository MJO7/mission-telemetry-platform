import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * A class component on purpose -- React only exposes the
 * componentDidCatch/getDerivedStateFromError lifecycle to class
 * components; there is no hook equivalent. This is the one place in the
 * app where that's unavoidable.
 *
 * Scope: this catches render-time errors in the component tree below it
 * (e.g. a bug in a page component). It does NOT catch errors inside
 * TanStack Query's async fetchers -- those surface through each query's
 * own `error` state instead, which is the correct place to show a
 * retry-able "failed to load" message rather than tearing down the page.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled error in component tree:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-3 px-6 text-center">
          <p className="text-lg font-medium text-slate-900">Something went wrong.</p>
          <p className="max-w-sm text-sm text-slate-500">
            The page hit an unexpected error. Reloading usually fixes it.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
