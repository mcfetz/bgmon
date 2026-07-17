<script lang="ts">
	let {
		open = $bindable(false),
		bestStreakHours = 0,
		bestStreakAchievedAt = null as string | null,
		currentStreakHours = 0,
		streakStartedAt = null as string | null
	}: {
		open?: boolean;
		bestStreakHours?: number | null;
		bestStreakAchievedAt?: string | null;
		currentStreakHours?: number | null;
		streakStartedAt?: string | null;
	} = $props();

	function close() {
		open = false;
	}

	function formatStreakHM(intervals: number | null | undefined): string {
		const v = intervals ?? 0;
		const totalMin = v * 15;
		const h = Math.floor(totalMin / 60);
		const m = totalMin % 60;
		return `${h}:${String(m).padStart(2, '0')}`;
	}

	function formatDateTime(iso: string | null | undefined): string {
		if (!iso) return '—';
		try {
			const d = new Date(iso);
			if (isNaN(d.getTime())) return '—';
			const date = d.toLocaleDateString('de-DE', {
				day: '2-digit',
				month: '2-digit',
				year: 'numeric'
			});
			const time = d.toLocaleTimeString('de-DE', {
				hour: '2-digit',
				minute: '2-digit'
			});
			return `${date} ${time}`;
		} catch {
			return '—';
		}
	}
</script>

{#if open}
	<button class="sm-backdrop" type="button" onclick={close} aria-label="Schließen"></button>
	<div class="sm-modal" role="dialog" aria-modal="true" aria-label="Streak">
		<header class="sm-header">
			<h2>Streak 🏆</h2>
			<button class="close-btn" type="button" onclick={close} aria-label="Schließen">×</button>
		</header>

		<div class="sm-body">
			<section class="sm-section">
				<h3 class="sm-section-title">Bester Streak</h3>
				<div class="sm-value-row">
					<span class="sm-value">{formatStreakHM(bestStreakHours)}</span>
					<span class="sm-unit">h:mm</span>
				</div>
				<p class="sm-meta">
					<time datetime={bestStreakAchievedAt ?? ''}>{formatDateTime(bestStreakAchievedAt)}</time>
				</p>
			</section>

			<section class="sm-section">
				<h3 class="sm-section-title">Aktueller Streak</h3>
				<div class="sm-value-row">
					<span class="sm-value">{formatStreakHM(currentStreakHours)}</span>
					<span class="sm-unit">h:mm</span>
				</div>
				<p class="sm-meta">
					seit <time datetime={streakStartedAt ?? ''}>{formatDateTime(streakStartedAt)}</time>
				</p>
			</section>
		</div>
	</div>
{/if}

<style>
	.sm-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 201;
		border: none;
		padding: 0;
		margin: 0;
		cursor: pointer;
		appearance: none;
		-webkit-appearance: none;
		color: transparent;
		outline: none;
	}

	.sm-backdrop:hover,
	.sm-backdrop:focus,
	.sm-backdrop:focus-visible,
	.sm-backdrop:active {
		background: rgba(0, 0, 0, 0.5);
		outline: none;
		box-shadow: none;
	}

	.sm-modal {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		background: var(--color-surface);
		border-radius: var(--radius);
		width: 90vw;
		max-width: 480px;
		max-height: 85vh;
		overflow-y: auto;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
		z-index: 202;
	}

	.sm-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--spacing-md);
		border-bottom: 1px solid var(--color-border);
	}

	.sm-header h2 {
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

	.sm-body {
		padding: var(--spacing-md);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-md);
	}

	.sm-section {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-xs);
		padding: var(--spacing-sm);
		background: rgba(var(--color-primary-rgb), 0.08);
		border-radius: var(--radius);
	}

	.sm-section-title {
		margin: 0;
		font-size: 0.75rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.sm-value-row {
		display: flex;
		align-items: baseline;
		gap: var(--spacing-xs);
	}

	.sm-value {
		font-size: 2.4rem;
		font-weight: 700;
		color: var(--color-primary);
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}

	.sm-unit {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.sm-meta {
		margin: 0;
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}
</style>
