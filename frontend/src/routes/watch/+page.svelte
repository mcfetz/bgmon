<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchCurrent } from '$lib/api/dashboard';

	let current = $state<{ sgv: number | null; direction: string | null } | null>(null);
	let lastUpdate = $state<string | null>(null);
	let error = $state('');

	onMount(() => {
		loadCurrent();
		const interval = setInterval(loadCurrent, 30_000);
		return () => clearInterval(interval);
	});

	async function loadCurrent() {
		try {
			const cur = await fetchCurrent();
			if (cur) {
				current = { sgv: cur.sgv, direction: cur.direction };
				lastUpdate = cur.timestamp;
			}
			error = '';
		} catch (e) {
			error = 'Fehler';
		}
	}

	function glucoseColor(sgv: number | null): string {
		if (sgv === null) return '#94a3b8';
		if (sgv < 70) return '#ef4444';
		if (sgv > 180) return '#f59e0b';
		return '#22c55e';
	}

	function trendArrow(direction: string | null): string {
		const arrows: Record<string, string> = {
			DoubleDown: '↓↓', SingleDown: '↓', FortyFiveDown: '↘',
			Flat: '→', FortyFiveUp: '↗', SingleUp: '↑', DoubleUp: '↑↑',
		};
		return arrows[direction ?? ''] ?? '';
	}
</script>

<div class="watch">
	<div class="value" style="color: {glucoseColor(current?.sgv ?? null)}">
		<span class="sgv">{current?.sgv ?? '---'}</span>
		<span class="trend">{trendArrow(current?.direction ?? null)}</span>
	</div>
	{#if lastUpdate}
		<div class="time">
			{new Date(lastUpdate).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
		</div>
	{/if}
	{#if error}
		<div class="error">{error}</div>
	{/if}
</div>

<style>
	.watch {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 100vh;
		gap: var(--spacing-sm);
		padding: var(--spacing-md);
	}

	.value {
		display: flex;
		align-items: center;
		gap: var(--spacing-xs);
	}

	.sgv {
		font-size: 4rem;
		font-weight: 800;
		line-height: 1;
	}

	.trend {
		font-size: 1.5rem;
	}

	.time {
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.error {
		font-size: 0.8rem;
		color: #f87171;
	}
</style>
