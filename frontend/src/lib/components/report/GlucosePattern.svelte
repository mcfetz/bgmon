<script lang="ts">
	import type { DailyProfile, GlucosePoint } from '$lib/api/report';
	import { clampGlucose, glucoseTrace, type GlucoseTrace } from './chart';

	let { profiles }: { profiles: DailyProfile[] } = $props();

	const width = 860;
	const height = 346;
	const pad = { top: 18, right: 24, bottom: 66, left: 52 };
	const chartWidth = width - pad.left - pad.right;
	const chartHeight = height - pad.top - pad.bottom;
	const periods = [
		{ label: 'Über Nacht', start: 0, end: 6 },
		{ label: 'Morgens', start: 6, end: 12 },
		{ label: 'Nachmittags', start: 12, end: 18 },
		{ label: 'Abends', start: 18, end: 24 }
	];

	function xScale(minutes: number): number {
		return pad.left + (minutes / 1440) * chartWidth;
	}

	function yScale(value: number): number {
		return pad.top + chartHeight - (clampGlucose(value) / 350) * chartHeight;
	}

	function trace(readings: GlucosePoint[]): GlucoseTrace {
		return glucoseTrace(readings, xScale, yScale);
	}

	const hasReadings = $derived(profiles.some((profile) => profile.readings.length > 0));
</script>

<div class="pattern-container">
	<svg
		viewBox={`0 0 ${width} ${height}`}
		class="pattern-svg"
		role="img"
		aria-label="Überlagerte Glukosekurven aller Tage"
	>
		<rect
			x={pad.left}
			y={yScale(180)}
			width={chartWidth}
			height={yScale(70) - yScale(180)}
			fill="#dcefdc"
		/>
		{#each [0, 54, 70, 180, 250, 350] as value}
			<line
				x1={pad.left}
				y1={yScale(value)}
				x2={pad.left + chartWidth}
				y2={yScale(value)}
				class:threshold={value === 70 || value === 180}
				class="grid"
			/>
			<text x={pad.left - 7} y={yScale(value) + 3.5} text-anchor="end" class="axis">{value}</text>
		{/each}
		{#each periods as period}
			<line
				x1={xScale(period.start * 60)}
				y1={pad.top}
				x2={xScale(period.start * 60)}
				y2={pad.top + chartHeight}
				class="vertical"
			/>
			<text x={xScale(period.start * 60)} y={height - 32} text-anchor="middle" class="axis"
				>{String(period.start).padStart(2, '0')}:00</text
			>
			<text
				x={xScale(((period.start + period.end) / 2) * 60)}
				y={height - 10}
				text-anchor="middle"
				class="period-label">{period.label}</text
			>
		{/each}
		<line
			x1={xScale(1440)}
			y1={pad.top}
			x2={xScale(1440)}
			y2={pad.top + chartHeight}
			class="vertical"
		/>
		<text x={xScale(1440)} y={height - 32} text-anchor="middle" class="axis">24:00</text>
		<text x={pad.left} y={12} class="unit">mg/dL</text>
		<text x={pad.left + 5} y={yScale(126)} class="target-label">Zielbereich</text>

		{#each profiles as profile}
			{@const chart = trace(profile.readings)}
			{#each chart.segments as segment}
				<path
					d={segment.d}
					fill="none"
					stroke={segment.color}
					stroke-width="1.05"
					stroke-linecap="round"
					opacity="0.5"
				/>
			{/each}
			{#each chart.points as point}
				<circle
					cx={point.cx}
					cy={point.cy}
					r="2.8"
					fill={point.color}
					stroke="#fff"
					stroke-width="0.8"
				>
					<title>{point.label}</title>
				</circle>
			{/each}
			{#each chart.compressionPoints as point}
				<circle cx={point.cx} cy={point.cy} r="3" class="compression-point">
					<title>{point.label}</title>
				</circle>
			{/each}
			{#each chart.caps as cap}
				<path d={cap.d} fill={cap.color} stroke="#fff" stroke-width="0.65" opacity="0.8">
					<title>{cap.label}</title>
				</path>
			{/each}
		{/each}
	</svg>
	{#if !hasReadings}
		<p class="no-data">Keine Glukosewerte im ausgewählten Zeitraum.</p>
	{/if}
	<div class="legend" aria-label="Legende">
		<span><i class="in-range"></i>70-180 mg/dL</span>
		<span><i class="high"></i>180-250 mg/dL</span>
		<span><i class="low"></i>&lt; 70 mg/dL oder &gt; 250 mg/dL</span>
		<span><i class="compression"></i>Möglicher Kompressionswert</span>
		<span><i class="target"></i>Hintergrund: Zielbereich</span>
	</div>
</div>

<style>
	.pattern-container {
		width: 100%;
		min-width: 0;
	}

	.pattern-svg {
		display: block;
		width: 100%;
		height: auto;
		min-width: 540px;
	}

	.grid,
	.vertical {
		stroke: #d7e0e2;
		stroke-width: 0.8;
		stroke-dasharray: 3 3;
	}

	.threshold {
		stroke: #6d9e70;
		stroke-width: 1.2;
		stroke-dasharray: none;
	}

	.axis,
	.unit,
	.target-label {
		font-size: 10px;
		fill: #506a74;
	}

	.unit {
		font-weight: 700;
	}

	.target-label {
		font-size: 9px;
		fill: #3e7748;
	}

	.period-label {
		font-size: 10px;
		fill: #385661;
		font-weight: 700;
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.3rem 0.9rem;
		margin-top: 0.2rem;
		font-size: 0.7rem;
		color: #405c67;
	}

	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}

	.legend i {
		display: inline-block;
		width: 0.78rem;
		height: 0.18rem;
		border-radius: 99px;
	}

	.in-range {
		background: #4f9d57;
	}

	.high {
		background: #d99a11;
	}

	.low {
		background: #b42318;
	}

	.compression {
		box-sizing: border-box;
		width: 0.58rem !important;
		height: 0.58rem !important;
		background: #fff;
		border: 1.4px solid #66767c;
	}

	.compression-point {
		fill: #fff;
		stroke: #66767c;
		stroke-width: 1.5;
	}

	.target {
		height: 0.58rem !important;
		background: #dcefdc;
		border: 1px solid #8db18e;
	}

	.no-data {
		margin: 0.35rem 0 0;
		text-align: center;
		font-size: 0.78rem;
		color: #6b7e85;
	}

	@media (max-width: 600px) {
		.pattern-container {
			overflow-x: auto;
		}
	}

	@media print {
		.pattern-container {
			overflow: visible !important;
		}

		.pattern-svg {
			min-width: 0;
		}

		.legend {
			font-size: 7pt;
		}
	}
</style>
