<script lang="ts">
	import type { DailyPatternPoint } from '$lib/api/report';
	import { areaPaths, clampGlucose, glucoseRangeCapMarkers, linePath } from './chart';

	let { points }: { points: DailyPatternPoint[] } = $props();

	const width = 860;
	const height = 405;
	const pad = { top: 18, right: 24, bottom: 47, left: 52 };
	const chartWidth = width - pad.left - pad.right;
	const glucoseHeight = 214;
	const treatmentTop = pad.top + glucoseHeight + 43;
	const treatmentHeight = 60;

	function xScale(index: number): number {
		return pad.left + (index / Math.max(points.length, 1)) * chartWidth;
	}

	function yScale(value: number): number {
		return pad.top + glucoseHeight - (clampGlucose(value) / 350) * glucoseHeight;
	}

	function values(key: 'p5' | 'p25' | 'p50' | 'p75' | 'p95'): (number | null)[] {
		const series = points.map((point) => point[key]);
		return points.at(-1)?.time_label === '23:30' ? [...series, series.at(-1) ?? null] : series;
	}

	const outerAreas = $derived(areaPaths(values('p5'), values('p95'), xScale, yScale));
	const innerAreas = $derived(areaPaths(values('p25'), values('p75'), xScale, yScale));
	const medianPath = $derived(linePath(values('p50'), xScale, yScale));
	const glucoseCaps = $derived(
		glucoseRangeCapMarkers(
			[values('p5'), values('p25'), values('p50'), values('p75'), values('p95')],
			xScale,
			yScale
		)
	);
	const maxTreatment = $derived(
		Math.max(
			1,
			...points.flatMap((point) => [
				point.carbs_avg,
				point.rapid_insulin_avg,
				point.basal_insulin_avg
			])
		)
	);
	const timeTicks = $derived([
		...points
			.filter((_, index) => index % 4 === 0)
			.map((point, index) => ({ index: index * 4, label: point.time_label })),
		{ index: points.length, label: '24:00' }
	]);
	const hasGlucose = $derived(points.some((point) => point.p50 !== null));

	function treatmentY(value: number): number {
		return treatmentTop + treatmentHeight - (value / maxTreatment) * treatmentHeight;
	}
</script>

<div class="daily-pattern">
	<svg
		viewBox={`0 0 ${width} ${height}`}
		class="daily-pattern-svg"
		role="img"
		aria-label="Tagesmuster mit Glukose und protokollierten Mengen"
	>
		<rect
			x={pad.left}
			y={yScale(180)}
			width={chartWidth}
			height={yScale(70) - yScale(180)}
			fill="#dcefdc"
		/>
		{#each [0, 70, 180, 250, 350] as value}
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
		{#each timeTicks as tick}
			<line
				x1={xScale(tick.index)}
				y1={pad.top}
				x2={xScale(tick.index)}
				y2={treatmentTop + treatmentHeight}
				class="vertical"
			/>
			<text x={xScale(tick.index)} y={height - 11} text-anchor="middle" class="axis"
				>{tick.label}</text
			>
		{/each}
		<text x={pad.left} y={11} class="unit">Glukose mg/dL</text>
		{#each outerAreas as path}<path d={path} fill="#c9d5e7" opacity="0.7" />{/each}
		{#each innerAreas as path}<path d={path} fill="#8ca8cb" opacity="0.72" />{/each}
		<path d={medianPath} fill="none" stroke="#176b87" stroke-width="2.4" />
		{#each glucoseCaps as cap}
			<path d={cap.d} fill={cap.color} stroke="#fff" stroke-width="0.8">
				<title>{cap.label}</title>
			</path>
		{/each}
		<text x={pad.left} y={treatmentTop - 26} class="treatment-label"
			>Durchschnittliche protokollierte Mengen je Tageszeit</text
		>
		<line
			x1={pad.left}
			y1={treatmentTop + treatmentHeight}
			x2={pad.left + chartWidth}
			y2={treatmentTop + treatmentHeight}
			class="treatment-baseline"
		/>
		{#each points as point, index}
			<rect
				x={xScale(index) - 4}
				y={treatmentY(point.carbs_avg)}
				width="2.5"
				height={treatmentTop + treatmentHeight - treatmentY(point.carbs_avg)}
				fill="#b57600"
			/>
			<rect
				x={xScale(index) - 0.75}
				y={treatmentY(point.rapid_insulin_avg)}
				width="2.5"
				height={treatmentTop + treatmentHeight - treatmentY(point.rapid_insulin_avg)}
				fill="#176b87"
			/>
			<rect
				x={xScale(index) + 2.5}
				y={treatmentY(point.basal_insulin_avg)}
				width="2.5"
				height={treatmentTop + treatmentHeight - treatmentY(point.basal_insulin_avg)}
				fill="#5c4b8a"
			/>
		{/each}
		<text x={pad.left} y={treatmentTop + 10} class="bar-label">KH</text>
		<text x={pad.left} y={treatmentTop + 21} class="bar-label">Schnell</text>
		<text x={pad.left} y={treatmentTop + 32} class="bar-label">Basal</text>
	</svg>
	{#if !hasGlucose}<p class="no-data">Keine Glukosewerte im ausgewählten Zeitraum.</p>{/if}
	<div class="legend">
		<span><i class="outer"></i>5.-95. Perzentil</span><span
			><i class="inner"></i>25.-75. Perzentil</span
		><span><i class="median"></i>Median</span><span><i class="carbs"></i>KH g/Tag</span><span
			><i class="rapid"></i>Schnellinsulin E/Tag</span
		><span><i class="basal"></i>Basalinsulin E/Tag</span>
	</div>
</div>

<style>
	.daily-pattern {
		width: 100%;
		min-width: 0;
		max-width: 100%;
	}

	.daily-pattern-svg {
		display: block;
		width: 100%;
		height: auto;
		min-width: 560px;
	}

	.grid,
	.vertical {
		stroke: #d7e0e2;
		stroke-width: 0.8;
		stroke-dasharray: 3 3;
	}

	.threshold {
		stroke: #6d9e70;
		stroke-width: 1.1;
		stroke-dasharray: none;
	}

	.axis,
	.unit,
	.treatment-label,
	.bar-label {
		font-size: 10px;
		fill: #506a74;
	}

	.unit,
	.treatment-label {
		font-weight: 700;
	}

	.bar-label {
		font-size: 7px;
	}

	.treatment-baseline {
		stroke: #7e9299;
		stroke-width: 1;
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.3rem 0.8rem;
		margin-top: 0.25rem;
		font-size: 0.67rem;
		color: #536b75;
	}

	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.22rem;
	}

	.legend i {
		display: inline-block;
		width: 0.7rem;
		height: 0.55rem;
		border-radius: 0.1rem;
	}

	.outer {
		background: #c9d5e7;
	}
	.inner {
		background: #8ca8cb;
	}
	.median {
		height: 0.18rem !important;
		background: #176b87;
	}
	.carbs {
		background: #b57600;
	}
	.rapid {
		background: #176b87;
	}
	.basal {
		background: #5c4b8a;
	}

	.no-data {
		margin: 0.35rem 0 0;
		text-align: center;
		font-size: 0.78rem;
		color: #6b7e85;
	}

	@media (max-width: 600px) {
		.daily-pattern {
			overflow-x: auto;
		}
	}

	@media print {
		.daily-pattern {
			overflow: visible !important;
		}

		.daily-pattern-svg {
			min-width: 0;
		}

		.legend {
			font-size: 6.5pt;
		}
	}
</style>
