import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  onDismiss: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class InspectorErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('Inspector rendering error:', error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'var(--bg-popup)',
            border: '1px solid var(--accent-red)',
            borderRadius: '8px',
            padding: '20px',
            zIndex: 1100,
            maxWidth: '320px',
            textAlign: 'center',
          }}
        >
          <h4 style={{ margin: '0 0 8px', color: 'var(--accent-red)' }}>Inspector Error</h4>
          <p style={{ margin: '0 0 12px', fontSize: '13px', opacity: 0.8 }}>
            Failed to render agent details. The data may be temporarily unavailable.
          </p>
          <button
            onClick={this.props.onDismiss}
            style={{
              background: 'var(--accent-red)',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 16px',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            Dismiss
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
