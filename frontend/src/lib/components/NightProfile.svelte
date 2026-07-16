<script lang="ts">
	import { apiFetch } from '$lib/auth';
	import { onMount } from 'svelte';

	interface Profile {
		enabled: boolean;
		start_time: string;
		end_time: string;
		webhook_token: string;
	}

	let profile = $state<Profile | null>(null);
	let loading = $state(false);
	let error = $state('');
	let saved = $state(false);

	onMount(() => {
		loadProfile();
	});

	async function loadProfile() {
		const res = await apiFetch('/api/night/profile');
		if (res.ok) {
			profile = await res.json();
		}
	}

	async function save() {
		if (!profile) return;
		loading = true;
		error = '';
		saved = false;
		const res = await apiFetch('/api/night/profile', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				enabled: profile.enabled,
				start_time: profile.start_time,
				end_time: profile.end_time
			})
		});
		if (res.ok) {
			saved = true;
			profile = await res.json();
		} else {
			const err = await res.json();
			error = err.error || 'Fehler';
		}
		loading = false;
	}
</script>

<div class="night-panel">
	<h2>Nachtprofil</h2>
	{#if error}
		<div class="error">{error}</div>
	{/if}
	{#if saved}
		<div class="success">Gespeichert.</div>
	{/if}
	{#if profile}
		<div class="field">
			<label for="night-enabled">
				<input id="night-enabled" type="checkbox" bind:checked={profile.enabled} />
				Aktiviert
			</label>
		</div>
		<div class="field">
			<label for="night-start">Start</label>
			<input id="night-start" type="time" bind:value={profile.start_time} />
		</div>
		<div class="field">
			<label for="night-end">Ende</label>
			<input id="night-end" type="time" bind:value={profile.end_time} />
		</div>
		{#if profile.webhook_token}
			<div class="webhook">
				Webhook: <code>{profile.webhook_token}</code>
			</div>
		{/if}
		<button onclick={save} disabled={loading}>
			{loading ? 'Speichern...' : 'Speichern'}
		</button>
	{:else}
		<p class="status">Lade...</p>
	{/if}
</div>

<style>
	.night-panel {
		background: var(--color-surface);
		padding: var(--spacing-md);
		border-radius: var(--radius);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-sm);
	}

	.night-panel h2 {
		font-size: 1.1rem;
		margin: 0;
		color: var(--color-text);
	}

	.field {
		display: flex;
		align-items: center;
		gap: var(--spacing-sm);
		font-size: 0.9rem;
	}

	.field label {
		color: var(--color-text-muted);
	}

	.field input[type='time'] {
		padding: var(--spacing-xs) var(--spacing-sm);
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
	}

	.webhook {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		word-break: break-all;
	}

	.webhook code {
		background: var(--color-bg);
		padding: 2px 4px;
		border-radius: 4px;
	}

	button {
		padding: var(--spacing-xs) var(--spacing-md);
		font-size: 0.9rem;
		background: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
		border: none;
		border-radius: var(--radius);
		cursor: pointer;
		width: fit-content;
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.status {
		font-size: 0.9rem;
		color: var(--color-text-muted);
		margin: 0;
	}

	.success {
		color: #4ade80;
		font-size: 0.85rem;
	}

	.error {
		color: #f87171;
		font-size: 0.85rem;
	}
</style>
