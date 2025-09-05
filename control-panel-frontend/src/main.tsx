import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';

// Note: StrictMode disabled due to race condition with deck.gl/luma.gl WebGL
// device initialization. StrictMode double-mounts components which can cause
// ResizeObserver to fire before WebGL context is ready, resulting in:
// "Cannot read properties of undefined (reading 'maxTextureDimension2D')"
// See: https://github.com/visgl/deck.gl/issues/9379
createRoot(document.getElementById('root')!).render(<App />);
