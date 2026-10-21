import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'node:fs';

const backend = process.env.BUSSURE_BACKEND || 'http://127.0.0.1:8000';
const https = process.env.BUSSURE_HTTPS === '1' ? {
  cert: fs.readFileSync('../.certs/local.pem'), key: fs.readFileSync('../.certs/local-key.pem'),
} : undefined;
const proxy = { '/api': { target: backend }, '/ws': { target: backend, ws: true } };
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1', port: 5173, strictPort: true, https, proxy,
    allowedHosts: ['mrithulas-macbook-neo.tail571945.ts.net'],
  },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, https, proxy },
});
