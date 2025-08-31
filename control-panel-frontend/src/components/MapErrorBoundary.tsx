import { Component, type ReactNode, type ErrorInfo } from 'react';
import styles from './Map.module.css';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class MapErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('Map rendering error:', error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      const isWebGLError =
        this.state.error?.message?.includes('WebGL') ||
        this.state.error?.message?.includes('maxTextureDimension') ||
        this.state.error?.message?.includes('getContext');

      return (
        <div className={styles['map-container']}>
          <div className={styles['map-error']}>
            <h3>Map Unavailable</h3>
            {isWebGLError ? (
              <p>
                WebGL is not supported or disabled in your browser. The map visualization requires
                WebGL to render. Please try using a modern browser like Chrome, Firefox, or Edge
                with hardware acceleration enabled.
              </p>
            ) : (
              <p>
                An error occurred while rendering the map. Please refresh the page to try again.
              </p>
            )}
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className={styles['retry-button']}
            >
              Retry
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
