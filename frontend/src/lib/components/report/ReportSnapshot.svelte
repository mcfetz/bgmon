<script lang="ts">
	import type { ReportSnapshot as SnapshotType, ReportPeriod } from '$lib/api/report';

	let { snapshot, period }: { snapshot: SnapshotType; period: ReportPeriod } = $props();
</script>

<div class="snapshot-grid">
	<div class="snapshot-left">
		<div class="stat-row">
			<span class="stat-label">Glukose-Durchschnitt</span>
			<span class="stat-value">{snapshot.mean_sgv ?? '–'} mg/dL</span>
		</div>
		<div class="stat-row">
			<span class="stat-label">GMI</span>
			<span class="stat-value">{snapshot.gmi ?? '–'}% / {snapshot.gmi !== null ? Math.round((snapshot.gmi - 2.15) / 0.0915 + 13.5) : '–'} mmol/mol</span>
		</div>
		<div class="stat-row">
			<span class="stat-label">% im Zielbereich</span>
			<span class="stat-value">{snapshot.tir_percent ?? '–'}%</span>
		</div>
		<div class="stat-row">
			<span class="stat-label">% über Zielbereich</span>
			<span class="stat-value">{snapshot.above_percent ?? '–'}%</span>
		</div>
		<div class="stat-row">
			<span class="stat-label">% unter Zielbereich</span>
			<span class="stat-value">{snapshot.below_percent ?? '–'}%</span>
		</div>
	</div>

	<div class="snapshot-right">
		<div class="stat-row">
			<span class="stat-label">Ereignisse mit niedrigem Glukosewert</span>
			<span class="stat-value">{snapshot.low_events_count}</span>
		</div>
		{#if snapshot.low_events_avg_duration_minutes !== null}
			<div class="stat-row">
				<span class="stat-label">Durchschnittliche Dauer</span>
				<span class="stat-value">{snapshot.low_events_avg_duration_minutes} Min.</span>
			</div>
		{/if}
		<div class="stat-row">
			<span class="stat-label">Sensor aktiv</span>
			<span class="stat-value">{snapshot.sensor_active_percent ?? '–'}%</span>
		</div>
		<div class="stat-row">
			<span class="stat-label">Durchschnittliche Scans/Ansichten</span>
			<span class="stat-value">{snapshot.avg_scans_per_day ?? '–'} / Tag</span>
		</div>
		{#if snapshot.carbs_daily_avg_grams !== null}
			<div class="stat-row">
				<span class="stat-label">KH-Durchschnitt</span>
				<span class="stat-value">{snapshot.carbs_daily_avg_grams} g/Tag</span>
			</div>
		{/if}
		{#if snapshot.insulin_daily_avg_units !== null}
			<div class="stat-row">
				<span class="stat-label">Insulin-Durchschnitt</span>
				<span class="stat-value">{snapshot.insulin_daily_avg_units} E/Tag</span>
			</div>
		{/if}
	</div>
</div>

{#if snapshot.low_events.length > 0}
	<div class="low-events">
		<h4>Niedrigglukose-Ereignisse</h4>
		<table class="events-table">
			<thead>
				<tr>
					<th>Datum</th>
					<th>Zeit</th>
					<th>Wert (mg/dL)</th>
					<th>Dauer</th>
				</tr>
			</thead>
			<tbody>
				{#each snapshot.low_events as event}
					<tr>
						<td>{event.date}</td>
						<td>{event.time}</td>
						<td class="low-val">{event.sgv}</td>
						<td>{event.duration_minutes} Min.</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<style>
	.snapshot-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.5rem;
	}
	.stat-row {
		display: flex;
		justify-content: space-between;
		padding: 0.3rem 0;
		border-bottom: 1px solid var(--color-border, #f0f0f0);
		font-size: 0.85rem;
	}
	.stat-label {
		color: var(--color-text-muted, #666);
	}
	.stat-value {
		font-weight: 600;
	}
	.low-events {
		margin-top: 1rem;
	}
	.low-events h4 {
		font-size: 0.85rem;
		margin: 0 0 0.5rem 0;
	}
	.events-table {
		border-collapse: collapse;
		font-size: 0.8rem;
		width: 100%;
		max-width: 400px;
	}
	.events-table th,
	.events-table td {
		border: 1px solid var(--color-border, #e5e7eb);
		padding: 0.3rem 0.5rem;
		text-align: left;
	}
	.events-table th {
		background: var(--color-surface-secondary, #f8f9fa);
		font-weight: 600;
	}
	.low-val {
		color: #dc2626;
		font-weight: 600;
	}
	@media (max-width: 600px) {
		.snapshot-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
