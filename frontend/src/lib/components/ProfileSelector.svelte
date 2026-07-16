<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/auth';

	interface NotificationProfile {
		id: number;
		name: string;
		icon: string;
		is_active: boolean;
		assignments: { id?: number; area: string; threshold: string }[];
	}

	let profiles = $state<NotificationProfile[]>([]);
	let activeId = $state<number | null>(null);
	let open = $state(false);
	let loading = $state(false);

	async function load() {
		loading = true;
		try {
			const [profilesRes, activeRes] = await Promise.all([
				apiFetch('/api/notifications/profiles'),
				apiFetch('/api/notifications/active')
			]);
			if (profilesRes.ok) {
				profiles = await profilesRes.json();
			}
			if (activeRes.ok) {
				const data = await activeRes.json();
				activeId = data.profile_id;
			}
		} catch (e) {
			console.error('Failed to load profiles:', e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		load();
	});

	const activeProfile = $derived(profiles.find((p) => p.id === activeId) ?? null);

	async function selectProfile(id: number) {
		open = false;
		try {
			const res = await apiFetch('/api/notifications/active', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ profile_id: id })
			});
			if (res.ok) {
				activeId = id;
			}
		} catch (e) {
			console.error('Failed to set active profile:', e);
		}
	}
</script>

<button
	class="profile-trigger"
	type="button"
	onclick={() => (open = !open)}
	title="Benachrichtigungs-Profil wählen"
	disabled={loading || profiles.length === 0}
>
	<span class="profile-icon">{activeProfile?.icon ?? '🔔'}</span>
</button>

{#if open}
	<div
		class="modal-backdrop"
		onclick={(e) => {
			if (e.target === e.currentTarget) open = false;
		}}
	>
		<div class="profile-modal">
			<div class="profile-modal-header">
				<h3>Benachrichtigungs-Profil wählen</h3>
				<button class="close-btn" type="button" onclick={() => (open = false)}>×</button>
			</div>
			<div class="profile-modal-body">
				{#if profiles.length === 0}
					<p class="hint">Keine Profile vorhanden. Erstelle eines in den Settings.</p>
				{:else}
					{#each profiles as profile (profile.id)}
						<button
							class="profile-option"
							class:active={profile.id === activeId}
							type="button"
							onclick={() => selectProfile(profile.id)}
						>
							<span class="profile-icon">{profile.icon}</span>
							<span class="profile-name">{profile.name}</span>
							{#if profile.id === activeId}
								<span class="check">✓</span>
							{/if}
						</button>
					{/each}
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.profile-trigger {
		width: 60px;
		height: 60px;
		border-radius: 50%;
		background: var(--color-bg);
		color: var(--color-text);
		font-size: 1.5rem;
		border: 1px solid var(--color-border-default);
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s ease;
		box-shadow: var(--shadow-sm);
	}

	.profile-trigger:hover:not(:disabled) {
		background: var(--color-border-subtle);
		transform: scale(1.05);
	}

	.profile-trigger:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.profile-icon {
		font-size: 1.75rem;
		line-height: 1;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
		padding: var(--spacing-md);
		overflow-y: auto;
	}

	.profile-modal {
		background: var(--color-surface);
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius);
		width: 100%;
		max-width: 360px;
		max-height: calc(100vh - 2rem);
		overflow-y: auto;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
		margin: auto;
	}

	.profile-modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--spacing-md);
		border-bottom: 1px solid var(--color-border-default);
	}

	.profile-modal-header h3 {
		margin: 0;
		font-size: 1.1rem;
		color: var(--color-text);
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		font-size: 1.5rem;
		cursor: pointer;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius);
		padding: 0;
	}

	.close-btn:hover {
		background: var(--color-border-subtle);
		color: var(--color-text);
	}

	.profile-modal-body {
		padding: var(--spacing-sm);
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.profile-option {
		display: flex;
		align-items: center;
		gap: var(--spacing-sm);
		padding: var(--spacing-sm) var(--spacing-md);
		background: transparent;
		color: var(--color-text);
		border: 1px solid transparent;
		border-radius: var(--radius);
		cursor: pointer;
		text-align: left;
		font-size: 1rem;
	}

	.profile-option:hover {
		background: var(--color-border-subtle);
	}

	.profile-option.active {
		background: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
		border-color: var(--color-primary);
	}

	.profile-option .profile-name {
		flex: 1;
	}

	.profile-option .check {
		font-weight: 700;
	}

	.hint {
		color: var(--color-text-muted);
		text-align: center;
		padding: var(--spacing-md);
	}
</style>
