<script lang="ts">
	import type { SmartAlert } from '#lib/api/dashboard.js';

	let { alerts = [] as SmartAlert[] }: { alerts?: SmartAlert[] } = $props();

	let expandedId = $state<string | null>(null);

	function toggle(id: string) {
		expandedId = expandedId === id ? null : id;
	}

	function formatTime(iso: string | null): string {
		if (!iso) return '';
		const date = new Date(iso);
		if (Number.isNaN(date.getTime())) return '';
		return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
	}
</script>

{#if alerts.length > 0}
	<div class="smart-alerts">
		<div class="smart-alerts-row">
			{#each alerts as alert (alert.id)}
				{@const isOpen = expandedId === alert.id}
				<button
					class="smart-alert-badge"
					class:open={isOpen}
					type="button"
					aria-expanded={isOpen}
					onclick={() => toggle(alert.id)}
				>
					<span class="badge-icon" aria-hidden="true">{alert.icon}</span>
					<span class="badge-title">{alert.title}</span>
					<svg
						class="badge-chevron"
						class:collapsed={!isOpen}
						width="12"
						height="12"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="3"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<polyline points="6 9 12 15 18 9"></polyline>
					</svg>
				</button>
			{/each}
		</div>

		{#each alerts as alert (alert.id)}
			{#if expandedId === alert.id}
				<div class="smart-alert-detail" role="status">
					<div class="detail-head">
						<span class="detail-title">{alert.icon} {alert.title}</span>
						{#if alert.created_at}
							<span class="detail-time">{formatTime(alert.created_at)}</span>
						{/if}
					</div>
					{#if alert.recommendation}
						<p class="detail-text">{alert.recommendation}</p>
					{/if}
				</div>
			{/if}
		{/each}
	</div>
{/if}

<style>
	.smart-alerts {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--spacing-xs);
		padding: 0 var(--spacing-md) var(--spacing-sm);
	}

	.smart-alerts-row {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 8px;
	}

	.smart-alert-badge {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		background: var(--color-warning);
		color: #fff;
		font-size: clamp(0.7rem, 1.5vw, 0.9rem);
		padding: 4px 10px;
		border: none;
		border-radius: 999px;
		font-weight: 600;
		font-family: inherit;
		cursor: pointer;
		max-width: min(90vw, 320px);
		text-align: left;
		line-height: 1.3;
	}

	.smart-alert-badge:active {
		transform: scale(0.98);
	}

	.smart-alert-badge.open {
		box-shadow:
			0 0 0 2px var(--color-surface),
			0 0 0 4px var(--color-warning);
	}

	.badge-icon {
		flex: 0 0 auto;
	}

	.badge-title {
		flex: 1 1 auto;
	}

	.badge-chevron {
		flex: 0 0 auto;
		opacity: 0.85;
		transition: transform 150ms ease-out;
	}

	.badge-chevron.collapsed {
		transform: rotate(-90deg);
	}

	.smart-alert-detail {
		max-width: min(92vw, 460px);
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-left: 3px solid var(--color-warning);
		border-radius: var(--radius);
		padding: var(--spacing-sm) var(--spacing-md);
		text-align: left;
	}

	.detail-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--spacing-sm);
		margin-bottom: var(--spacing-xs);
	}

	.detail-title {
		font-size: 0.85rem;
		font-weight: 700;
		color: var(--color-text);
	}

	.detail-time {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.detail-text {
		margin: 0;
		font-size: 0.85rem;
		line-height: 1.45;
		color: var(--color-text);
	}
</style>
