<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { applyUserColors, getStoredColors } from '$lib/theme';

	let { children } = $props();

	onMount(() => {
		const colors = getStoredColors();
		if (colors.mode === 'dark') {
			document.documentElement.setAttribute('data-theme', 'dark');
		} else if (colors.mode === 'light') {
			document.documentElement.setAttribute('data-theme', 'light');
		}
		applyUserColors(colors);

		if ('serviceWorker' in navigator) {
			navigator.serviceWorker.register('/service-worker.js').catch((err) => {
				console.error('Service worker registration failed:', err);
			});
		}
	});
</script>

<div class="app">
	{@render children?.()}
</div>

<style>
	.app {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
	}
</style>
