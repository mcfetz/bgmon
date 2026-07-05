<script lang="ts">
	import { onMount } from 'svelte';

	interface GlucoseCurrent {
		sgv: number | null;
		trend: number | null;
		direction: string | null;
		timestamp: string | null;
	}

	interface StatsData {
		mean: number | null;
		tir_percent: number | null;
		readings: number;
	}

	let token = $state('');
	let current = $state<GlucoseCurrent | null>(null);
	let stats = $state<StatsData | null>(null);
	let loading = $state(true);
	let error = $state('');

	onMount(() => {
		// Extract token from path: /family/<token>
		const path = window.location.pathname;
		const match = path.match(/^\/family\/([^/]+)/);
		token = match ? match[1] : '';
		if (token) {
			loadData();
			const interval = setInterval(loadData, 30_000);
			return () => clearInterval(interval);
		} else {
			loading = false;
			error = 'Kein Token in der URL.';
		}
	});

	async function loadData() {
		try {
			const res = await fetch(`/api/family/${token}`);
			if (!res.ok) {
				error = 'Ungültiger Token oder keine Daten.';
				loading = false;
				return;
			}
			const data = await res.json();
			current = data.current;
			stats = data.stats;
			error = '';
		} catch {
			error = 'Daten konnten nicht geladen werden.';
		} finally {
			loading = false;
		}
	}

	function trendArrow(direction: string | null): string {
		const arrows: Record<string, string> = {
			DoubleDown: '↓↓',
			SingleDown: '↓',
			FortyFiveDown: '↘',
			Flat: '→',
			FortyFiveUp: '↗',
			SingleUp: '↑',
			DoubleUp: '↑↑'
		};
		return arrows[direction ?? ''] ?? '';
	}

	function glucoseColor(sgv: number | null): string {
		if (sgv === null) return 'var(--color-text-muted)';
		if (sgv < 70) return '#ef4444';
		if (sgv > 180) return '#f59e0b';
		return '#22c55e';
	}
</script>

<div class="family-dashboard">
	<h1>Fiona - Glucose-Monitor</h1>

	{#if loading}
		<div class="loading">Lade...</div>
	{:else if error}
		<div class="error">{error}</div>
	{:else if current}
		<div class="current" style="color: {glucoseColor(current.sgv)}">
			<span class="sgv">{current.sgv ?? '---'}</span>
			<span class="unit">mg/dL</span>
			<span class="trend">{trendArrow(current.direction)}</span>
		</div>
	{/if}

	{#if stats}
		<div class="stats">
			<div class="stat">
				<span class="label">Ø Heute</span>
				<span class="value">{stats.mean ?? '---'} mg/dL</span>
			</div>
			<div class="stat">
				<span class="label">TIR</span>
				<span class="value">{stats.tir_percent ?? '---'}%</span>
			</div>
			<div class="stat">
				<span class="label">Messungen</span>
				<span class="value">{stats.readings}</span>
			</div>
		</div>
	{/if}
</div>

<style>
	.family-dashboard {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--spacing-lg);
		padding: var(--spacing-lg);
		max-width: 600px;
		margin: 0 auto;
		min-height: 100vh;
		justify-content: center;
	}

	h1 {
		font-size: 1.2rem;
		color: var(--color-text-muted);
		margin: 0;
	}

	.current {
		display: flex;
		align-items: baseline;
		gap: var(--spacing-xs);
	}

	.sgv {
		font-size: 5rem;
		font-weight: 800;
		line-height: 1;
	}

	.unit {
		font-size: 1.2rem;
		opacity: 0.7;
	}

	.trend {
		font-size: 2rem;
		margin-left: var(--spacing-sm);
	}

	.stats {
		display: flex;
		gap: var(--spacing-lg);
		justify-content: center;
	}

	.stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--spacing-xs);
	}

	.stat .label {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}

	.stat .value {
		font-size: 1.2rem;
		font-weight: 600;
		color: var(--color-text);
	}

	.loading {
		color: var(--color-text-muted);
		font-size: 1rem;
	}

	.error {
		color: #f87171;
		font-size: 1rem;
		text-align: center;
	}
</style>
