<script lang="ts">
	import type { GlucosePoint, WeeklyDay } from '$lib/api/report';
	import { clampGlucose, formatNumber, glucoseTrace, type GlucoseTrace } from './chart';

	let {
		days,
		readingsByDate
	}: {
		days: WeeklyDay[];
		readingsByDate: ReadonlyMap<string, GlucosePoint[]>;
	} = $props();

	const width = 400;
	const height = 62;
	const pad = { top: 4, right: 4, bottom: 13, left: 19 };
	const chartWidth = width - pad.left - pad.right;
	const chartHeight = height - pad.top - pad.bottom;

	function xScale(minutes: number): number {
		return pad.left + (minutes / 1440) * chartWidth;
	}

	function yScale(value: number): number {
		return pad.top + chartHeight - (clampGlucose(value) / 350) * chartHeight;
	}

	function trace(readings: GlucosePoint[]): GlucoseTrace {
		return glucoseTrace(readings, xScale, yScale);
	}

	function shortDate(date: string): string {
		return `${date.slice(8)}.${date.slice(5, 7)}.`;
	}
</script>

<div class="weekly-overview">
	<div class="weekly-heading">
		<span>Tag</span><span>Glukoseverlauf</span><span>Durchschnitt</span><span>KH</span><span
			>Gesamtinsulin</span
		><span>Niedrige Ereignisse</span><span>Abdeckung</span>
	</div>
	{#each days as day}
		{@const readings = readingsByDate.get(day.date) ?? []}
		{@const chart = trace(readings)}
		<article class="week-row">
			<div class="week-label" aria-label={`Tag ${day.weekday} ${shortDate(day.date)}`}>
				<strong>{day.weekday}</strong><span>{shortDate(day.date)}</span>
			</div>
			<div class="week-chart">
				<svg
					viewBox={`0 0 ${width} ${height}`}
					role="img"
					aria-label={`Glukoseverlauf ${day.date}`}
				>
					<rect
						x={pad.left}
						y={yScale(180)}
						width={chartWidth}
						height={yScale(70) - yScale(180)}
						fill="#dcefdc"
					/>
					{#each [70, 180] as value}<line
							x1={pad.left}
							y1={yScale(value)}
							x2={pad.left + chartWidth}
							y2={yScale(value)}
							class="threshold"
						/>{/each}
					{#each [0, 360, 720, 1080, 1440] as minute}<line
							x1={xScale(minute)}
							y1={pad.top}
							x2={xScale(minute)}
							y2={pad.top + chartHeight}
							class="vertical"
						/>{/each}
					<text x={pad.left - 2} y={yScale(70) + 3} text-anchor="end" class="axis">70</text>
					<text x={pad.left - 2} y={yScale(180) + 3} text-anchor="end" class="axis">180</text>
					{#each chart.segments as segment}<path
							d={segment.d}
							fill="none"
							stroke={segment.color}
							stroke-width="1.3"
							stroke-linecap="round"
						/>{/each}
					{#each chart.points as point}
						<circle
							cx={point.cx}
							cy={point.cy}
							r="1.9"
							fill={point.color}
							stroke="#fff"
							stroke-width="0.65"
						>
							<title>{point.label}</title>
						</circle>
					{/each}
					{#each chart.compressionPoints as point}
						<circle cx={point.cx} cy={point.cy} r="2.15" class="compression-point">
							<title>{point.label}</title>
						</circle>
					{/each}
					{#each chart.caps as cap}
						<path d={cap.d} fill={cap.color} stroke="#fff" stroke-width="0.5">
							<title>{cap.label}</title>
						</path>
					{/each}
					<text x={pad.left} y={height - 2} class="axis">00</text><text
						x={xScale(720)}
						y={height - 2}
						text-anchor="middle"
						class="axis">12</text
					><text x={pad.left + chartWidth} y={height - 2} text-anchor="end" class="axis">24</text>
				</svg>
				{#if readings.length === 0}<span class="no-trace">Keine Glukosedaten</span>{/if}
			</div>
			<div
				class="week-value"
				aria-label={`Glukose-Durchschnitt: ${formatNumber(day.avg_sgv, 0)} mg/dL`}
			>
				<b>{formatNumber(day.avg_sgv, 0)}</b><small>mg/dL</small>
			</div>
			<div class="week-value" aria-label={`Kohlenhydrate: ${formatNumber(day.carbs_total)} g`}>
				<b>{formatNumber(day.carbs_total)}</b><small>g</small>
			</div>
			<div class="week-value" aria-label={`Gesamtinsulin: ${formatNumber(day.total_insulin)} E`}>
				<b>{formatNumber(day.total_insulin)}</b><small>E</small>
			</div>
			<div
				class:low={day.low_events > 0}
				class="week-value"
				aria-label={`Niedrige Ereignisse: ${day.low_events}`}
			>
				<b>{day.low_events}</b><small>Ereignisse</small>
			</div>
			<div
				class="week-value"
				aria-label={`Datenabdeckung: ${formatNumber(day.data_coverage_percent, 0)} %`}
			>
				<b>{formatNumber(day.data_coverage_percent, 0)} %</b><small>Abd.</small>
			</div>
		</article>
	{/each}
</div>
<footer class="weekly-legend"><span><i></i>Möglicher Kompressionswert</span></footer>

<style>
	.weekly-overview {
		display: grid;
		width: 100%;
		gap: 0.22rem;
		min-width: 0;
		max-width: 100%;
	}

	.weekly-heading,
	.week-row {
		display: grid;
		grid-template-columns: 3.7rem minmax(12rem, 1fr) 4.4rem 3.3rem 4.4rem 4.8rem 3.5rem;
		gap: 0.35rem;
		align-items: center;
	}

	.weekly-heading {
		padding: 0 0.2rem 0.16rem;
		font-size: 0.57rem;
		font-weight: 700;
		text-align: center;
		color: #58707a;
	}

	.weekly-heading span:nth-child(2) {
		text-align: left;
	}

	.weekly-heading span {
		overflow-wrap: anywhere;
	}

	.week-row {
		min-width: 590px;
		padding: 0.22rem;
		border: 1px solid #c9d5d8;
		border-radius: 0.32rem;
		background: #fff;
	}

	.week-label {
		display: grid;
		gap: 0.02rem;
		font-size: 0.7rem;
		color: #18313d;
	}

	.week-label span {
		font-size: 0.61rem;
		color: #58707a;
	}

	.week-chart {
		position: relative;
	}

	.week-chart svg {
		display: block;
		width: 100%;
		height: auto;
	}

	.threshold {
		stroke: #78a377;
		stroke-width: 0.7;
		stroke-dasharray: 2 2;
	}

	.vertical {
		stroke: #d5dfe1;
		stroke-width: 0.65;
		stroke-dasharray: 2 2;
	}

	.axis {
		font-size: 6px;
		fill: #607982;
	}

	.compression-point {
		fill: #fff;
		stroke: #66767c;
		stroke-width: 1.1;
	}

	.no-trace {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		font-size: 0.55rem;
		color: #6f8188;
	}

	.week-value {
		min-width: 0;
		text-align: center;
		font-variant-numeric: tabular-nums;
		color: #18313d;
	}

	.week-value b,
	.week-value small {
		display: block;
	}

	.week-value b {
		font-size: 0.73rem;
	}

	.week-value small {
		font-size: 0.5rem;
		color: #687d85;
	}

	.week-value.low b {
		color: #b42318;
	}

	.weekly-legend {
		margin-top: 0.3rem;
		font-size: 0.58rem;
		color: #536b75;
	}

	.weekly-legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
	}

	.weekly-legend i {
		box-sizing: border-box;
		width: 0.48rem;
		height: 0.48rem;
		border: 1.3px solid #66767c;
		border-radius: 99px;
		background: #fff;
	}

	@media (max-width: 760px) {
		.weekly-overview {
			overflow-x: auto;
		}
	}

	@media print {
		.weekly-overview {
			overflow: visible !important;
		}

		.weekly-heading,
		.week-row {
			grid-template-columns: 12mm minmax(36mm, 1fr) 13mm 10mm 13mm 15mm 16mm;
			gap: 1.2mm;
		}

		.week-row {
			min-width: 0;
			padding: 1mm;
		}

		.weekly-legend {
			margin-top: 1.2mm;
			font-size: 5.2pt;
		}
	}
</style>
