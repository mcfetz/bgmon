<script lang="ts">
	import { apiFetch } from '$lib/auth';
	import { onMount } from 'svelte';

	interface Shift {
		id: number;
		user_id: number;
		user_name: string;
		started_at: string;
	}

	let active = $state(false);
	let shift = $state<Shift | null>(null);
	let loading = $state(false);
	let error = $state('');

	onMount(() => {
		loadShift();
	});

	async function loadShift() {
		const res = await apiFetch('/api/shifts/active');
		if (res.ok) {
			const data = await res.json();
			active = data.active;
			shift = data.shift;
		}
	}

	async function startShift() {
		loading = true;
		error = '';
		const res = await apiFetch('/api/shifts/start', { method: 'POST' });
		if (res.ok) {
			await loadShift();
		} else {
			const err = await res.json();
			error = err.error || 'Fehler';
		}
		loading = false;
	}

	async function endShift() {
		loading = true;
		error = '';
		const res = await apiFetch('/api/shifts/end', { method: 'POST' });
		if (res.ok) {
			await loadShift();
		} else {
			const err = await res.json();
			error = err.error || 'Fehler';
		}
		loading = false;
	}
</script>

<div class="shift-panel">
	<h2>Schicht</h2>
	{#if error}
		<div class="error">{error}</div>
	{/if}
	{#if active && shift}
		<p class="status">
			Aktiv: {shift.user_name} (seit {new Date(shift.started_at).toLocaleTimeString('de-DE', {
				hour: '2-digit',
				minute: '2-digit'
			})})
		</p>
		<button onclick={endShift} disabled={loading}>
			{loading ? 'Wird beendet...' : 'Schicht beenden'}
		</button>
	{:else}
		<p class="status">Keine aktive Schicht</p>
		<button onclick={startShift} disabled={loading}>
			{loading ? 'Wird gestartet...' : 'Schicht übernehmen'}
		</button>
	{/if}
</div>

<style>
	.shift-panel {
		background: var(--color-surface);
		padding: var(--spacing-md);
		border-radius: var(--radius);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-sm);
	}

	.shift-panel h2 {
		font-size: 1.1rem;
		margin: 0;
		color: var(--color-text);
	}

	.status {
		font-size: 0.9rem;
		color: var(--color-text-muted);
		margin: 0;
	}

	button {
		padding: var(--spacing-xs) var(--spacing-md);
		font-size: 0.9rem;
		background: var(--color-primary);
		color: white;
		border: none;
		border-radius: var(--radius);
		cursor: pointer;
		width: fit-content;
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.error {
		color: #f87171;
		font-size: 0.85rem;
	}
</style>
