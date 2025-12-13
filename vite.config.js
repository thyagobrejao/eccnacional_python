import { defineConfig } from 'vite';

export default defineConfig({
    base: '/static/',
    server: {
        port: 5173,
        strictPort: true,
    },
    build: {
        manifest: true,
        outDir: 'static/dist',
        rollupOptions: {
            input: 'static/js/main.js',
        },
    },
});