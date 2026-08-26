<script lang="ts">
	import type { LowGlucoseEvent, ReportSnapshot as SnapshotType } from '$lib/api/report';
	import { formatGermanCalendarDate, formatLowGlucoseEventTime } from '$lib/utils/reportDates';
	import { formatNumber } from './chart';

	let {
		snapshot,
		lowEvents,
		showSummary = true
	}: {
		snapshot: SnapshotType;
		lowEvents?: LowGlucoseEvent[];
		showSummary?: boolean;
	} = $props();

	const coverageWidth = 430;
	const coverageHeight = 124;
	const coveragePad = { top: 18, right: 12, bottom: 28, left: 30 };
	const coverageChartWidth = coverageWidth - coveragePad.left - coveragePad.right;
	const coverageChartHeight = coverageHeight - coveragePad.top - coveragePad.bottom;

	function coverageX(index: number): number {
		return (
			coveragePad.left +
			(index / Math.max(snapshot.coverage_profile.length - 1, 1)) * coverageChartWidth
		);
	}

	function coverageY(value: number): number {
		return coveragePad.top + coverageChartHeight - (value / 100) * coverageChartHeight;
	}

	function coveragePath(): string {
		return snapshot.coverage_profile
			.map(
				(point, index) =>
					`${index === 0 ? 'M' : 'L'}${coverageX(index)},${coverageY(point.data_coverage_percent)}`
			)
			.join('');
	}

	function coverageArea(): string {
		if (snapshot.coverage_profile.length === 0) return '';
		const top = snapshot.coverage_profile.map(
			(point, index) => `${coverageX(index)},${coverageY(point.data_coverage_percent)}`
		);
		return `M${coverageX(0)},${coverageY(0)}L${top.join('L')}L${coverageX(snapshot.coverage_profile.length - 1)},${coverageY(0)}Z`;
	}

	const hasFood = $derived(snapshot.carbs_daily_avg > 0);
	const hasInsulin = $derived(
		snapshot.rapid_insulin_daily_avg > 0 || snapshot.basal_insulin_daily_avg > 0
	);
	const displayedLowEvents = $derived(lowEvents ?? snapshot.low_events);
	const duplicateLowEventTimes = $derived.by(() => {
		const counts = new Map<string, number>();
		for (const event of snapshot.low_events) {
			const key = `${event.date} ${event.time}`;
			counts.set(key, (counts.get(key) ?? 0) + 1);
		}

		const duplicates = new Set<string>();
		for (const [key, count] of counts) {
			if (count > 1) duplicates.add(key);
		}
		return duplicates;
	});

	function lowEventTime(event: LowGlucoseEvent): string {
		return formatLowGlucoseEventTime(
			event,
			duplicateLowEventTimes.has(`${event.date} ${event.time}`)
		);
	}
</script>

{#if showSummary}
	<div class="snapshot-layout">
		<section class="snapshot-summary">
			<div class="primary-value">
				<span>Glukose-Durchschnitt</span>
				<strong>{formatNumber(snapshot.mean_sgv)} <small>mg/dL</small></strong>
			</div>
			<div class="summary-grid">
				<div>
					<span>GMI</span><b>{formatNumber(snapshot.gmi)} %</b><small
						>{formatNumber(snapshot.gmi_mmol_mol, 0)} mmol/mol</small
					>
				</div>
				<div>
					<span>Im Zielbereich</span><b>{formatNumber(snapshot.tir_percent)} %</b><small
						>70-180 mg/dL</small
					>
				</div>
				<div>
					<span>Über Zielbereich</span><b>{formatNumber(snapshot.above_percent)} %</b><small
						>&gt; 180 mg/dL</small
					>
				</div>
				<div>
					<span>Unter Zielbereich</span><b>{formatNumber(snapshot.below_percent)} %</b><small
						>&lt; 70 mg/dL</small
					>
				</div>
			</div>
			<div class="low-summary">
				<div><span>Niedrige Ereignisse</span><b>{snapshot.low_events_count}</b></div>
				<div>
					<span>Mittlere Dauer</span><b
						>{snapshot.low_events_avg_duration_minutes === null
							? '-'
							: `${formatNumber(snapshot.low_events_avg_duration_minutes)} Min.`}</b
					>
				</div>
			</div>
		</section>

		<section class="coverage-panel">
			<div class="coverage-heading">
				<div><strong>Datenabdeckung</strong><span>Beobachtungsintervalle nach Tageszeit</span></div>
				<b>{formatNumber(snapshot.data_coverage_percent)} %</b>
			</div>
			<svg
				viewBox={`0 0 ${coverageWidth} ${coverageHeight}`}
				class="coverage-chart"
				role="img"
				aria-label="Datenabdeckung nach Tageszeit"
			>
				{#each [0, 50, 100] as value}
					<line
						x1={coveragePad.left}
						y1={coverageY(value)}
						x2={coveragePad.left + coverageChartWidth}
						y2={coverageY(value)}
						class="coverage-grid"
					/>
					<text
						x={coveragePad.left - 5}
						y={coverageY(value) + 3}
						text-anchor="end"
						class="coverage-axis">{value}</text
					>
				{/each}
				<path d={coverageArea()} fill="#c9e6eb" />
				<path d={coveragePath()} fill="none" stroke="#176b87" stroke-width="2" />
				{#each snapshot.coverage_profile as point, index}
					<circle
						cx={coverageX(index)}
						cy={coverageY(point.data_coverage_percent)}
						r="2"
						fill="#176b87"
					>
						<title
							>{point.time_start} bis {point.time_end}: {formatNumber(point.data_coverage_percent)} %</title
						>
					</circle>
				{/each}
				{#each snapshot.coverage_profile as point, index}
					{#if index % 3 === 0}
						<text
							x={coverageX(index)}
							y={coverageHeight - 8}
							text-anchor="middle"
							class="coverage-axis">{point.time_start}</text
						>
					{/if}
				{/each}
			</svg>
		</section>
	</div>

	<section class="treatment-section" aria-labelledby="treatment-title">
		<h3 id="treatment-title">Protokollierte Mahlzeiten und Insulinmengen pro Tag</h3>
		<div class="treatment-cards">
			<div class="treatment-card carbs">
				<span>Kohlenhydrate</span><b
					>{formatNumber(snapshot.carbs_daily_avg)} <small>g/Tag</small></b
				>
			</div>
			<div class="treatment-card rapid">
				<span>Schnellinsulin</span><b
					>{formatNumber(snapshot.rapid_insulin_daily_avg)} <small>E/Tag</small></b
				>
			</div>
			<div class="treatment-card basal">
				<span>Basalinsulin</span><b
					>{formatNumber(snapshot.basal_insulin_daily_avg)} <small>E/Tag</small></b
				>
			</div>
			<div class="treatment-card total">
				<span>Gesamtinsulin</span><b
					>{formatNumber(snapshot.total_insulin_daily_avg)} <small>E/Tag</small></b
				>
			</div>
		</div>
		<div class="recorded-states">
			{#if !hasFood}<p>Keine Kohlenhydrate im ausgewählten Zeitraum protokolliert.</p>{/if}
			{#if !hasInsulin}<p>Kein Insulin im ausgewählten Zeitraum protokolliert.</p>{/if}
			{#if hasFood || hasInsulin}<p>
					Die Werte zeigen ausschließlich protokollierte Einträge.
				</p>{/if}
		</div>
	</section>
{/if}

<section
	class="events-section"
	class:events-continuation={!showSummary}
	aria-label="Ereignisse mit niedrigem Glukosewert"
>
	<h3>{showSummary ? 'Ereignisse mit niedrigem Glukosewert' : 'Ereignisliste'}</h3>
	{#if showSummary && snapshot.low_events_truncated}
		<p class="events-truncated">
			Nur die ersten {snapshot.low_events.length} von insgesamt {snapshot.low_events_count} Ereignissen
			werden detailliert angezeigt.
		</p>
	{/if}
	{#if displayedLowEvents.length > 0}
		<div class="events-table-wrap">
			<table>
				<thead><tr><th>Datum</th><th>Zeit</th><th>Minimum</th><th>Beobachtete Dauer</th></tr></thead
				>
				<tbody>
					{#each displayedLowEvents as event}
						<tr
							><td>{formatGermanCalendarDate(event.date)}</td><td>{lowEventTime(event)}</td><td
								>{event.sgv} mg/dL</td
							><td>{event.duration_minutes} Min.</td></tr
						>
					{/each}
				</tbody>
			</table>
		</div>
	{:else}
		<p class="no-events">Keine Ereignisse mit Glukosewerten unter 70 mg/dL erkannt.</p>
	{/if}
</section>

<style>
	.snapshot-layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
		gap: 0.7rem;
	}

	.snapshot-summary,
	.coverage-panel,
	.treatment-section,
	.events-section {
		border: 1px solid #bdcbcf;
		border-radius: 0.45rem;
		background: #fff;
	}

	.snapshot-summary {
		padding: 0.7rem;
	}

	.primary-value {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		padding-bottom: 0.55rem;
		border-bottom: 1px solid #d5e0e2;
	}

	.primary-value span,
	.summary-grid span,
	.low-summary span,
	.treatment-card span,
	.coverage-heading span {
		display: block;
		font-size: 0.67rem;
		color: #58707a;
	}

	.primary-value strong {
		font-size: 1.28rem;
		color: #176b87;
	}

	.primary-value small,
	.treatment-card small {
		font-size: 0.55em;
		color: #405c67;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.55rem 0.7rem;
		padding: 0.6rem 0;
	}

	.summary-grid b,
	.low-summary b {
		display: block;
		margin-top: 0.08rem;
		font-size: 1rem;
		font-variant-numeric: tabular-nums;
		color: #18313d;
	}

	.summary-grid small {
		font-size: 0.57rem;
		color: #6b7e85;
	}

	.low-summary {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.7rem;
		padding-top: 0.5rem;
		border-top: 1px solid #d5e0e2;
	}

	.coverage-panel {
		padding: 0.7rem;
	}

	.coverage-heading {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
		align-items: center;
	}

	.coverage-heading strong {
		display: block;
		font-size: 0.8rem;
		color: #18313d;
	}

	.coverage-heading b {
		font-size: 1.08rem;
		color: #176b87;
	}

	.coverage-chart {
		display: block;
		width: 100%;
		height: auto;
		margin-top: 0.25rem;
	}

	.coverage-grid {
		stroke: #d5dfe1;
		stroke-width: 0.8;
		stroke-dasharray: 2 2;
	}

	.coverage-axis {
		font-size: 8px;
		fill: #607982;
	}

	.treatment-section,
	.events-section {
		margin-top: 0.7rem;
		padding: 0.65rem;
	}

	.events-section.events-continuation {
		margin-top: 0;
	}

	h3 {
		margin: 0 0 0.45rem;
		font-size: 0.8rem;
		color: #18313d;
	}

	.treatment-cards {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.4rem;
	}

	.treatment-card {
		min-height: 3.8rem;
		padding: 0.45rem;
		border-left: 0.25rem solid #8ca0a7;
		background: #f5f8f8;
	}

	.treatment-card.carbs {
		border-color: #b57600;
	}

	.treatment-card.rapid {
		border-color: #176b87;
	}

	.treatment-card.basal {
		border-color: #5c4b8a;
	}

	.treatment-card.total {
		border-color: #34515d;
	}

	.treatment-card b {
		display: block;
		margin-top: 0.35rem;
		font-size: 1.02rem;
		font-variant-numeric: tabular-nums;
		color: #18313d;
	}

	.recorded-states {
		margin-top: 0.45rem;
	}

	.recorded-states p,
	.no-events,
	.events-truncated {
		margin: 0.12rem 0;
		font-size: 0.68rem;
		color: #58707a;
	}

	.events-truncated {
		margin-bottom: 0.35rem;
	}

	.events-table-wrap {
		overflow-x: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.68rem;
	}

	th,
	td {
		padding: 0.28rem 0.38rem;
		border-top: 1px solid #dce5e7;
		text-align: left;
	}

	th {
		font-size: 0.62rem;
		color: #58707a;
	}

	td:nth-child(3) {
		color: #b42318;
		font-weight: 700;
	}

	@media (max-width: 680px) {
		.snapshot-layout {
			grid-template-columns: 1fr;
		}

		.treatment-cards {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media print {
		.snapshot-layout {
			grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr) !important;
			gap: 3mm;
		}

		.treatment-cards {
			grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
		}

		.snapshot-summary,
		.coverage-panel,
		.treatment-section,
		.events-section {
			border-radius: 1.2mm;
		}

		.events-section {
			margin-top: 3mm;
		}
	}
</style>
