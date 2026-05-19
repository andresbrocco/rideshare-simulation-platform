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
    rollupOptions: {
      output: {
        manualChunks: (id: string) => {
          if (id.includes('maplibre-gl')) return 'vendor-maplibre';
          if (
            id.includes('@deck.gl') ||
            id.includes('@luma.gl') ||
            id.includes('@loaders.gl') ||
            id.includes('@math.gl')
          )
            return 'vendor-deckgl';
          if (id.includes('react-map-gl')) return 'vendor-react-map-gl';
        },
      },
      onwarn(warning, warn) {
        if (warning.message?.includes('"spawn" is not exported by')) return;
        warn(warning);
      },
    },
  },
});
