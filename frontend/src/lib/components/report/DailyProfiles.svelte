<script lang="ts">
	import type { DailyProfile, GlucosePoint } from '$lib/api/report';
	import { clampGlucose, formatNumber, glucoseTrace, type GlucoseTrace } from './chart';

	let { profiles, compact = false }: { profiles: DailyProfile[]; compact?: boolean } = $props();

	const width = 180;
	const height = $derived(compact ? 52 : 82);
	const pad = $derived(
		compact
			? { top: 3, right: 3, bottom: 11, left: 15 }
			: { top: 5, right: 4, bottom: 15, left: 18 }
	);
	const chartWidth = $derived(width - pad.left - pad.right);
	const chartHeight = $derived(height - pad.top - pad.bottom);

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

<div class="daily-grid" class:compact>
	{#each profiles as profile}
		{@const chart = trace(profile.readings)}
		<article class="day-card">
			<header class="day-header">
				<div>
					<strong>{profile.weekday}</strong>
					<span>{shortDate(profile.date)}</span>
				</div>
				<strong class="day-average">{formatNumber(profile.avg, 0)} <small>mg/dL</small></strong>
			</header>
			<svg
				viewBox={`0 0 ${width} ${height}`}
				class="day-chart"
				role="img"
				aria-label={`Glukoseprofil ${profile.date}`}
			>
				<rect
					x={pad.left}
					y={yScale(180)}
					width={chartWidth}
					height={yScale(70) - yScale(180)}
					fill="#e1f1df"
				/>
				<line
					x1={pad.left}
					y1={yScale(70)}
					x2={pad.left + chartWidth}
					y2={yScale(70)}
					class="threshold"
				/>
				<line
					x1={pad.left}
					y1={yScale(180)}
					x2={pad.left + chartWidth}
					y2={yScale(180)}
					class="threshold"
				/>
				<line
					x1={xScale(720)}
					y1={pad.top}
					x2={xScale(720)}
					y2={pad.top + chartHeight}
					class="midday"
				/>
				<text x={pad.left - 2} y={yScale(70) + 3} text-anchor="end" class="axis">70</text>
				<text x={pad.left - 2} y={yScale(180) + 3} text-anchor="end" class="axis">180</text>
				{#each chart.segments as segment}
					<path
						d={segment.d}
						fill="none"
						stroke={segment.color}
						stroke-width="1.35"
						stroke-linecap="round"
					/>
				{/each}
				{#each chart.points as point}
					<circle
						cx={point.cx}
						cy={point.cy}
						r="2.15"
						fill={point.color}
						stroke="#fff"
						stroke-width="0.75"
					>
						<title>{point.label}</title>
					</circle>
				{/each}
				{#each chart.compressionPoints as point}
					<circle cx={point.cx} cy={point.cy} r="2.45" class="compression-point">
						<title>{point.label}</title>
					</circle>
				{/each}
				{#each chart.caps as cap}
					<path d={cap.d} fill={cap.color} stroke="#fff" stroke-width="0.55">
						<title>{cap.label}</title>
					</path>
				{/each}
				<text x={pad.left} y={height - 3} class="axis">00</text>
				<text x={xScale(720)} y={height - 3} text-anchor="middle" class="axis">12</text>
				<text x={pad.left + chartWidth} y={height - 3} text-anchor="end" class="axis">24</text>
			</svg>
			{#if profile.readings.length === 0}
				<p class="empty-trace">Keine Glukosedaten</p>
			{/if}
			{#if !compact}
				<footer class="day-meta">
					<span>Abd. {formatNumber(profile.data_coverage_percent)} %</span>
					<span>KH {formatNumber(profile.carbs_total)} g</span>
					<span>Ins. {formatNumber(profile.total_insulin)} E</span>
					{#if profile.low_events > 0}<span class="low-events">Niedrig {profile.low_events}</span
						>{/if}
				</footer>
			{:else if profile.low_events > 0}
				<span class="compact-low">Niedrig {profile.low_events}</span>
			{/if}
		</article>
	{/each}
</div>

<style>
	.daily-grid {
		display: grid;
		grid-template-columns: repeat(7, minmax(0, 1fr));
		gap: 0.35rem;
	}

	.day-card {
		position: relative;
		min-width: 0;
		border: 1px solid #c6d2d5;
		border-radius: 0.34rem;
		padding: 0.28rem;
		background: #fff;
	}

	.day-header {
		display: flex;
		justify-content: space-between;
		gap: 0.25rem;
		align-items: baseline;
		min-height: 1.65rem;
		font-size: 0.69rem;
		color: #18313d;
	}

	.day-header div {
		display: grid;
		gap: 0.02rem;
	}

	.day-header span,
	.day-average small {
		font-size: 0.58rem;
		color: #58707a;
	}

	.day-average {
		text-align: right;
		white-space: nowrap;
		font-size: 0.72rem;
		font-variant-numeric: tabular-nums;
		color: #176b87;
	}

	.day-chart {
		display: block;
		width: 100%;
		height: auto;
	}

	.threshold {
		stroke: #83a980;
		stroke-width: 0.6;
		stroke-dasharray: 2 2;
	}

	.midday {
		stroke: #cbd8da;
		stroke-width: 0.6;
		stroke-dasharray: 2 2;
	}

	.axis {
		font-size: 7px;
		fill: #607982;
	}

	.compression-point {
		fill: #fff;
		stroke: #66767c;
		stroke-width: 1.2;
	}

	.empty-trace {
		position: absolute;
		top: 2.35rem;
		left: 0.5rem;
		right: 0.5rem;
		margin: 0;
		text-align: center;
		font-size: 0.59rem;
		color: #6b7e85;
	}

	.day-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.08rem 0.32rem;
		margin-top: 0.08rem;
		font-size: 0.54rem;
		line-height: 1.2;
		color: #58707a;
	}

	.low-events {
		color: #b42318;
		font-weight: 700;
	}

	.compact-low {
		display: block;
		margin-top: 0.04rem;
		font-size: 0.51rem;
		font-weight: 700;
		color: #b42318;
	}

	.daily-grid.compact .day-header {
		min-height: 1.15rem;
		font-size: 0.63rem;
	}

	.daily-grid.compact .day-header span,
	.daily-grid.compact .day-average small {
		font-size: 0.5rem;
	}

	.daily-grid.compact .day-average {
		font-size: 0.66rem;
	}

	@media (max-width: 900px) {
		.daily-grid {
			grid-template-columns: repeat(4, minmax(0, 1fr));
		}
	}

	@media (max-width: 620px) {
		.daily-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.55rem;
		}

		.day-card {
			padding: 0.45rem;
		}

		.day-meta {
			font-size: 0.64rem;
		}
	}

	@media print {
		.daily-grid {
			grid-template-columns: repeat(7, minmax(0, 1fr)) !important;
			gap: 1.4mm;
		}

		.day-card {
			border-radius: 1.1mm;
			padding: 1.1mm;
		}

		.day-header {
			font-size: 6.5pt;
		}

		.day-meta {
			font-size: 5pt;
		}

		.daily-grid.compact .day-card {
			padding: 0.8mm;
		}

		.daily-grid.compact .compact-low {
			font-size: 4.3pt;
		}
	}
</style>
