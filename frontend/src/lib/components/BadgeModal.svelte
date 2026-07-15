<script lang="ts">
	type Achievement = {
		id: string;
		name: string;
		icon: string;
		description: string;
		unlocked: boolean;
	};

	let {
		open = $bindable(false),
		achievements = [] as Achievement[]
	}: {
		open?: boolean;
		achievements?: Achievement[];
	} = $props();

	function close() {
		open = false;
	}

	const unlockedCount = $derived(achievements.filter((a) => a.unlocked).length);
	const totalCount = $derived(achievements.length);
</script>

{#if open}
	<button class="badge-modal-backdrop" type="button" onclick={close} aria-label="Schließen"
	></button>
	<div class="badge-modal" role="dialog" aria-modal="true" aria-label="Badges">
		<header class="badge-header">
			<h2>Badges 🏅</h2>
			<button class="close-btn" type="button" onclick={close} aria-label="Schließen">×</button>
		</header>

		<div class="badge-body">
			<p class="badge-progress">{unlockedCount} von {totalCount} freigeschaltet</p>

			<div class="badge-grid">
				{#each achievements as a}
					<div class="badge-card" class:locked={!a.unlocked}>
						<span class="badge-icon">{a.unlocked ? a.icon : '🔒'}</span>
						<span class="badge-name">{a.name}</span>
						<span class="badge-desc">{a.description}</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
{/if}

<style>
	.badge-modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 100;
		border: none;
		padding: 0;
		margin: 0;
		cursor: pointer;
		appearance: none;
		-webkit-appearance: none;
		color: transparent;
		outline: none;
	}

	.badge-modal-backdrop:hover,
	.badge-modal-backdrop:focus,
	.badge-modal-backdrop:focus-visible,
	.badge-modal-backdrop:active {
		background: rgba(0, 0, 0, 0.5);
		outline: none;
		box-shadow: none;
	}

	.badge-modal {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		background: var(--color-surface);
		border-radius: var(--radius);
		width: 90vw;
		max-width: 520px;
		max-height: 85vh;
		overflow-y: auto;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
		z-index: 101;
	}

	.badge-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--spacing-md);
		border-bottom: 1px solid var(--color-border);
	}

	.badge-header h2 {
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
	}

	.close-btn:hover {
		background: var(--color-bg);
		color: var(--color-text);
	}

	.badge-body {
		padding: var(--spacing-md);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-md);
	}

	.badge-progress {
		text-align: center;
		color: var(--color-text-muted);
		font-size: 0.85rem;
		margin: 0;
	}

	.badge-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: var(--spacing-sm);
	}

	.badge-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		padding: var(--spacing-sm);
		background: rgba(var(--color-primary-rgb), 0.08);
		border-radius: var(--radius);
		text-align: center;
	}

	.badge-card.locked {
		background: var(--color-bg);
		opacity: 0.6;
	}

	.badge-icon {
		font-size: 2rem;
	}

	.badge-name {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-text);
	}

	.badge-card.locked .badge-name {
		color: var(--color-text-muted);
	}

	.badge-desc {
		font-size: 0.7rem;
		color: var(--color-text-muted);
	}
</style>
