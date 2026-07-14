import React from 'react';

// Without this, an uncaught render error anywhere in the tree unmounts the whole app and
// React shows nothing (a blank page) in production. This catches it and shows a generic,
// friendly message instead - the real error (with component stack) only ever goes to the
// browser console for debugging, never onto the page itself.
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('Unhandled UI error:', error, info?.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6 text-center">
          <div>
            <h1 className="text-2xl font-display font-bold">Something went wrong</h1>
            <p className="text-muted-foreground mt-2">Please refresh the page. If this keeps happening, contact us.</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 inline-flex items-center justify-center rounded-md px-4 py-2 bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90"
            >
              Refresh
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
