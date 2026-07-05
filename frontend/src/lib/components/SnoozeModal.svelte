<script lang="ts">
	import { apiFetch } from '$lib/auth';

	type SnoozeState = {
		active: boolean;
		snooze_until: string | null;
		reason: string | null;
	};

	let { open = $bindable(false), onUpdate }: { open?: boolean; onUpdate?: () => void } = $props();

	let snooze = $state<SnoozeState>({ active: false, snooze_until: null, reason: null });
	let loading = $state(false);
	let error = $state('');

	async function fetchSnooze() {
		const res = await apiFetch('/api/notifications/snooze');
		if (res.ok) snooze = await res.json();
	}

	$effect(() => {
		if (open) {
			fetchSnooze();
			error = '';
		}
	});

	function remainingMinutes(): number {
		if (!snooze.snooze_until) return 0;
		return Math.max(0, Math.ceil((new Date(snooze.snooze_until).getTime() - Date.now()) / 60000));
	}

	async function setSnooze(minutes: number) {
		loading = true;
		error = '';
		const res = await apiFetch('/api/notifications/snooze', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ minutes })
		});
		loading = false;
		if (!res.ok) {
			error = 'Fehler beim Setzen';
			return;
		}
		snooze = await res.json();
		onUpdate?.();
	}

	async function adjustSnooze(delta: number) {
		loading = true;
		error = '';
		const res = await apiFetch('/api/notifications/snooze', {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ delta_minutes: delta })
		});
		loading = false;
		if (!res.ok) {
			error = 'Fehler beim Anpassen';
			return;
		}
		snooze = await res.json();
		onUpdate?.();
	}

	async function stopSnooze() {
		loading = true;
		error = '';
		const res = await apiFetch('/api/notifications/snooze', { method: 'DELETE' });
		loading = false;
		if (!res.ok) {
			error = 'Fehler beim Stoppen';
			return;
		}
		open = false;
		onUpdate?.();
	}
</script>

{#if open}
	<div class="modal-backdrop" onclick={() => (open = false)} role="presentation"></div>
	<div class="modal" role="dialog" aria-modal="true" aria-label="Snooze anpassen">
		<header class="modal-header">
			<h2>Snooze</h2>
			<button class="close-btn" type="button" onclick={() => (open = false)} aria-label="Schließen"
				>×</button
			>
		</header>

		{#if error}
			<p class="error">{error}</p>
		{/if}

		<div class="current">
			{#if snooze.active}
				<span class="current-label">läuft noch</span>
				<span class="current-time">{remainingMinutes()} min</span>
			{:else}
				<span class="current-label">kein aktiver Snooze</span>
			{/if}
		</div>

		<div class="presets">
			<button class="preset-btn" type="button" onclick={() => setSnooze(15)} disabled={loading}>
				<span class="preset-value">15</span>
				<span class="preset-unit">min</span>
			</button>
			<button class="preset-btn" type="button" onclick={() => setSnooze(30)} disabled={loading}>
				<span class="preset-value">30</span>
				<span class="preset-unit">min</span>
			</button>
			<button class="preset-btn" type="button" onclick={() => setSnooze(60)} disabled={loading}>
				<span class="preset-value">60</span>
				<span class="preset-unit">min</span>
			</button>
		</div>

		<div class="adjust">
			<button
				class="adjust-btn"
				type="button"
				onclick={() => adjustSnooze(-5)}
				disabled={loading || !snooze.active}
			>
				−5 min
			</button>
			<button
				class="adjust-btn"
				type="button"
				onclick={() => adjustSnooze(5)}
				disabled={loading || !snooze.active}
			>
				+5 min
			</button>
		</div>

		<button
			class="stop-btn"
			type="button"
			onclick={stopSnooze}
			disabled={loading || !snooze.active}
		>
			Snooze stoppen
		</button>
	</div>
{/if}

<style>
	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.4);
		z-index: 100;
	}

	.modal {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		background: var(--color-surface);
		border-radius: var(--radius-lg, 16px);
		padding: var(--spacing-md);
		min-width: 280px;
		max-width: 360px;
		width: calc(100vw - 32px);
		z-index: 101;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-md);
	}

	.modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.modal-header h2 {
		margin: 0;
		font-size: 1.1rem;
	}

	.close-btn {
		background: transparent;
		color: var(--color-text-muted);
		font-size: 1.5rem;
		padding: 0;
		width: 28px;
		height: 28px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		line-height: 1;
	}

	.close-btn:hover {
		background: var(--color-border-subtle);
	}

	.error {
		color: #f87171;
		font-size: 0.85rem;
		margin: 0;
	}

	.current {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		padding: var(--spacing-sm) 0;
		background: var(--color-bg);
		border-radius: var(--radius);
	}

	.current-label {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.current-time {
		font-size: 1.5rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.presets {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: var(--spacing-sm);
	}

	.preset-btn {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
		padding: var(--spacing-sm);
		background: var(--color-bg);
		color: var(--color-text);
		border-radius: var(--radius);
		border: 1px solid var(--color-border-default);
	}

	.preset-btn:hover:not(:disabled) {
		background: var(--color-border-subtle);
		border-color: var(--color-primary);
	}

	.preset-value {
		font-size: 1.25rem;
		font-weight: 700;
	}

	.preset-unit {
		font-size: 0.7rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
	}

	.adjust {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--spacing-sm);
	}

	.adjust-btn {
		padding: var(--spacing-sm);
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius);
		font-weight: 600;
	}

	.adjust-btn:hover:not(:disabled) {
		background: var(--color-border-subtle);
	}

	.stop-btn {
		padding: var(--spacing-sm);
		background: var(--color-danger);
		color: white;
		border: none;
		border-radius: var(--radius);
		font-weight: 600;
	}

	.stop-btn:hover:not(:disabled) {
		background: #dc2626;
	}

	button:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
