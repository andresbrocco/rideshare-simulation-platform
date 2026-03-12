import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import svgr from 'vite-plugin-svgr';

export default defineConfig({
  plugins: [react(), svgr()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['landing.local', 'control-panel.local'],
    watch: {
      usePolling: true,
    },
    proxy: {
      '/api': {
        target: 'http://simulation:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: 'ws://simulation:8000',
        ws: true,
      },
      '/localstack': {
        target: 'http://localstack:4566',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/localstack/, ''),
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.removeHeader('Origin');
            proxyReq.removeHeader('Referer');
          });
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
