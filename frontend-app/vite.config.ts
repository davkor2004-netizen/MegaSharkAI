import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000';

  return {
    plugins: [sveltekit()],
    server: {
      port: 3000,
      host: '0.0.0.0',
      strictPort: true,
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        '/media': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        '/ws': {
          target: apiProxyTarget,
          changeOrigin: true,
          ws: true
        }
      }
    },
    optimizeDeps: {
      include: ['svelte']
    }
  };
});
