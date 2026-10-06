import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [
		sveltekit({
			preprocess: vitePreprocess(),
			adapter: adapter({
				fallback: 'index.html',
				pages: 'dist',
				assets: 'dist',
				precompress: false,
				strict: true
			}),
			prerender: {
				entries: ['/', '/login', '/settings', '/log', '/users', '/family', '/watch']
			}
		})
	],
	test: {
		include: ['src/**/*.{test,spec}.{js,ts}']
	},
	server: {
		allowedHosts: true,
		proxy: {
			'/api': {
				target: 'http://localhost:5000',
				changeOrigin: true
			},
			'/health': {
				target: 'http://localhost:5000',
				changeOrigin: true
			}
		}
	},
	preview: {
		allowedHosts: true
	}
});
