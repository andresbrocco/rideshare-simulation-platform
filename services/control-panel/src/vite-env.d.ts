/// <reference types="vite/client" />
/// <reference types="vite-plugin-svgr/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_WS_URL: string;
  readonly VITE_LAMBDA_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
