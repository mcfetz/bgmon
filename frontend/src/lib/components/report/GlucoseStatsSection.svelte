<script lang="ts">
	import type { GlucoseStats, ReportPeriod } from '$lib/api/report';

	let { stats, period }: { stats: GlucoseStats; period: ReportPeriod } = $props();

	const bands = $derived([
		{ label: 'Sehr niedrig', sub: '<54 mg/dL', percent: stats.time_below_54 ?? 0, color: '#dc2626' },
		{ label: 'Niedrig', sub: '54–69 mg/dL', percent: stats.time_54_70 ?? 0, color: '#f97316' },
		{ label: 'Zielbereich', sub: '70–180 mg/dL', percent: stats.time_70_180 ?? 0, color: '#22c55e' },
		{ label: 'Hoch', sub: '181–250 mg/dL', percent: stats.time_180_250 ?? 0, color: '#eab308' },
		{ label: 'Sehr hoch', sub: '>250 mg/dL', percent: stats.time_above_250 ?? 0, color: '#dc2626' }
	]);
</script>

<div class="stats-grid">
	<div class="tir-section">
		<h3>Zeit in Bereichen</h3>
		<div class="tir-bar">
			{#each bands as band}
				{#if band.percent > 0}
					<div
						class="tir-segment"
						style="width: {band.percent}%; background: {band.color}"
						title="{band.label}: {band.percent}%"
					></div>
				{/if}
			{/each}
		</div>
		<div class="tir-labels">
			{#each bands as band}
				<div class="tir-label" style="color: {band.color}">
					<span class="pct">{band.percent}%</span>
					<span class="sub">{band.sub}</span>
				</div>
			{/each}
		</div>
	</div>

	<div class="metrics-grid">
		<div class="metric">
			<span class="metric-value">{stats.mean ?? '–'}</span>
			<span class="metric-label">Glukose-Durchschnitt (mg/dL)</span>
		</div>
		<div class="metric">
			<span class="metric-value">{stats.gmi ?? '–'}%</span>
			<span class="metric-label">GMI (Glukose-Managementindikator)</span>
		</div>
		<div class="metric">
			<span class="metric-value">{stats.cv_percent ?? '–'}%</span>
			<span class="metric-label">Variabilität (VK%)</span>
		</div>
		<div class="metric">
			<span class="metric-value">{stats.sensor_active_percent ?? '–'}%</span>
			<span class="metric-label">Sensor aktiv</span>
		</div>
	</div>
</div>

<style>
	.stats-grid {
		display: grid;
		gap: 1.5rem;
	}
	.tir-section h3 {
		font-size: 0.9rem;
		margin: 0 0 0.5rem 0;
	}
	.tir-bar {
		display: flex;
		height: 24px;
		border-radius: 4px;
		overflow: hidden;
		margin-bottom: 0.5rem;
	}
	.tir-segment {
		transition: width 0.3s;
	}
	.tir-labels {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
	}
	.tir-label {
		display: flex;
		flex-direction: column;
		font-size: 0.8rem;
	}
	.tir-label .pct {
		font-weight: 700;
		font-size: 1rem;
	}
	.tir-label .sub {
		font-size: 0.7rem;
		opacity: 0.8;
	}
	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 1rem;
	}
	.metric {
		display: flex;
		flex-direction: column;
		text-align: center;
		padding: 0.75rem;
		background: var(--color-surface-secondary, #f8f9fa);
		border-radius: 8px;
	}
	.metric-value {
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--color-primary, #3b82f6);
	}
	.metric-label {
		font-size: 0.75rem;
		color: var(--color-text-muted, #666);
		margin-top: 0.25rem;
	}
</style>
