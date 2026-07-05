<script lang="ts">
	type StatsData = {
		tir_below?: number | null;
		tir_percent?: number | null;
		tir_above?: number | null;
		readings?: number;
	} | null;

	let {
		open = $bindable(false),
		stats = null as StatsData
	}: {
		open?: boolean;
		stats?: StatsData;
	} = $props();

	function close() {
		open = false;
	}
</script>

{#if open}
	<button class="tir-modal-backdrop" type="button" onclick={close} aria-label="Schließen"></button>
	<div class="tir-modal" role="dialog" aria-modal="true" aria-label="Time in Range">
		<header class="tir-header">
			<h2>Time in Range</h2>
			<button class="close-btn" type="button" onclick={close} aria-label="Schließen">×</button>
		</header>

		<div class="tir-big-value">
			{stats?.tir_percent ?? '—'}<span class="tir-big-unit">%</span>
		</div>
		<p class="tir-subtitle">im grünen Bereich (70–180 mg/dL)</p>

		<div class="tir-bar-large">
			<div class="tir-segment below" style="width: {stats?.tir_below ?? 0}%">
				{#if (stats?.tir_below ?? 0) >= 5}<span class="tir-label"
						>{stats?.tir_below?.toFixed(1) ?? 0}%</span
					>{/if}
			</div>
			<div class="tir-segment range" style="width: {stats?.tir_percent ?? 0}%">
				{#if (stats?.tir_percent ?? 0) >= 5}<span class="tir-label"
						>{stats?.tir_percent?.toFixed(1) ?? 0}%</span
					>{/if}
			</div>
			<div class="tir-segment above" style="width: {stats?.tir_above ?? 0}%">
				{#if (stats?.tir_above ?? 0) >= 5}<span class="tir-label"
						>{stats?.tir_above?.toFixed(1) ?? 0}%</span
					>{/if}
			</div>
		</div>

		<div class="tir-legend">
			<div class="legend-item">
				<span class="legend-swatch below"></span>
				<div>
					<div class="legend-label">Niedrig (&lt; 70 mg/dL)</div>
					<div class="legend-value">{stats?.tir_below?.toFixed(1) ?? 0}%</div>
				</div>
			</div>
			<div class="legend-item">
				<span class="legend-swatch range"></span>
				<div>
					<div class="legend-label">Im Bereich (70–180 mg/dL)</div>
					<div class="legend-value">{stats?.tir_percent?.toFixed(1) ?? 0}%</div>
				</div>
			</div>
			<div class="legend-item">
				<span class="legend-swatch above"></span>
				<div>
					<div class="legend-label">Hoch (&gt; 180 mg/dL)</div>
					<div class="legend-value">{stats?.tir_above?.toFixed(1) ?? 0}%</div>
				</div>
			</div>
		</div>

		<p class="tir-footer">
			Basierend auf {stats?.readings ?? 0} Messwerten · Klick außerhalb zum Schließen
		</p>
	</div>
{/if}

<style>
	.tir-modal-backdrop {
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

	.tir-modal-backdrop:hover,
	.tir-modal-backdrop:focus,
	.tir-modal-backdrop:focus-visible,
	.tir-modal-backdrop:active {
		background: rgba(0, 0, 0, 0.5);
		outline: none;
		box-shadow: none;
	}

	.tir-modal {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: min(90vw, 480px);
		background: var(--color-surface);
		border-radius: var(--radius-lg, 20px);
		z-index: 101;
		padding: var(--spacing-lg, 24px);
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-md);
	}

	.tir-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.tir-header h2 {
		margin: 0;
		font-size: 1.1rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
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
		line-height: 1;
	}

	.close-btn:hover {
		background: var(--color-bg);
		color: var(--color-text);
	}

	.tir-big-value {
		font-size: 4rem;
		font-weight: 800;
		line-height: 1;
		text-align: center;
		color: #22c55e;
		font-variant-numeric: tabular-nums;
	}

	.tir-big-unit {
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin-left: 4px;
	}

	.tir-subtitle {
		text-align: center;
		color: var(--color-text-muted);
		font-size: 0.85rem;
		margin: 0;
	}

	.tir-bar-large {
		display: flex;
		height: 48px;
		border-radius: 12px;
		overflow: hidden;
		gap: 2px;
	}

	.tir-segment {
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
		font-size: 0.85rem;
		color: #1a1a1a;
		min-width: 0;
	}

	.tir-segment.below {
		background: #f97316;
	}
	.tir-segment.range {
		background: #22c55e;
	}
	.tir-segment.above {
		background: #eab308;
	}

	.tir-label {
		white-space: nowrap;
		overflow: hidden;
	}

	.tir-legend {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-sm);
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: var(--spacing-sm);
	}

	.legend-swatch {
		width: 16px;
		height: 16px;
		border-radius: 4px;
		flex-shrink: 0;
	}

	.legend-swatch.below {
		background: #f97316;
	}
	.legend-swatch.range {
		background: #22c55e;
	}
	.legend-swatch.above {
		background: #eab308;
	}

	.legend-label {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.legend-value {
		font-size: 1rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.tir-footer {
		text-align: center;
		color: var(--color-text-muted);
		font-size: 0.75rem;
		margin: 0;
		opacity: 0.7;
	}
</style>
