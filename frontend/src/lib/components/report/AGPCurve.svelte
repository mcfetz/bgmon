<script lang="ts">
	import type { AGPPoint } from '$lib/api/report';
	import { areaPaths, clampGlucose, glucoseRangeCapMarkers, linePath } from './chart';

	let { points, compact = false }: { points: AGPPoint[]; compact?: boolean } = $props();

	const width = 860;
	const height = 330;
	const pad = { top: 18, right: 24, bottom: 46, left: 52 };
	const chartWidth = width - pad.left - pad.right;
	const chartHeight = height - pad.top - pad.bottom;

	function xScale(index: number): number {
		return pad.left + (index / Math.max(points.length, 1)) * chartWidth;
	}

	function timeX(hour: number): number {
		return pad.left + (hour / 24) * chartWidth;
	}

	function yScale(value: number): number {
		return pad.top + chartHeight - (clampGlucose(value) / 350) * chartHeight;
	}

	function extendFinalBucket(values: (number | null)[]): (number | null)[] {
		return points.at(-1)?.time_label === '23:30' ? [...values, values.at(-1) ?? null] : values;
	}

	const p5 = $derived(extendFinalBucket(points.map((point) => point.p5)));
	const p25 = $derived(extendFinalBucket(points.map((point) => point.p25)));
	const p50 = $derived(extendFinalBucket(points.map((point) => point.p50)));
	const p75 = $derived(extendFinalBucket(points.map((point) => point.p75)));
	const p95 = $derived(extendFinalBucket(points.map((point) => point.p95)));
	const outerAreas = $derived(areaPaths(p5, p95, xScale, yScale));
	const innerAreas = $derived(areaPaths(p25, p75, xScale, yScale));
	const medianPath = $derived(linePath(p50, xScale, yScale));
	const lowerPath = $derived(linePath(p5, xScale, yScale));
	const upperPath = $derived(linePath(p95, xScale, yScale));
	const glucoseCaps = $derived(glucoseRangeCapMarkers([p5, p25, p50, p75, p95], xScale, yScale));
	const hasData = $derived(points.some((point) => point.p50 !== null));
	const timeTicks = [0, 3, 6, 9, 12, 15, 18, 21, 24];
</script>

<div class="agp-container" class:compact>
	<svg
		viewBox={`0 0 ${width} ${height}`}
		class="agp-svg"
		role="img"
		aria-label="Ambulantes Glukoseprofil"
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
				class:value-threshold={value === 70 || value === 180}
				class="grid-line"
			/>
			<text x={pad.left - 7} y={yScale(value) + 3.5} text-anchor="end" class="axis-label"
				>{value}</text
			>
		{/each}
		{#each timeTicks as hour}
			<line
				x1={timeX(hour)}
				y1={pad.top}
				x2={timeX(hour)}
				y2={pad.top + chartHeight}
				class="vertical-grid"
			/>
			<text x={timeX(hour)} y={height - 11} text-anchor="middle" class="axis-label">
				{String(hour).padStart(2, '0')}:00
			</text>
		{/each}
		<text x={pad.left} y={12} class="unit-label">mg/dL</text>
		<text x={pad.left + 5} y={yScale(125)} class="target-label">Zielbereich 70-180</text>

		{#each outerAreas as path}
			<path d={path} fill="#f5cf75" opacity="0.46" />
		{/each}
		{#each innerAreas as path}
			<path d={path} fill="#8fc98b" opacity="0.7" />
		{/each}
		<path d={lowerPath} fill="none" stroke="#d7a92e" stroke-width="1" stroke-dasharray="4 3" />
		<path d={upperPath} fill="none" stroke="#d7a92e" stroke-width="1" stroke-dasharray="4 3" />
		<path d={medianPath} fill="none" stroke="#236c4a" stroke-width="2.4" stroke-linejoin="round" />
		{#each glucoseCaps as cap}
			<path d={cap.d} fill={cap.color} stroke="#fff" stroke-width="0.8">
				<title>{cap.label}</title>
			</path>
		{/each}
	</svg>
	{#if !hasData}
		<p class="no-data">Keine Glukosewerte im ausgewählten Zeitraum.</p>
	{/if}
	<div class="agp-summary" aria-label="Perzentillegende">
		<span><i class="outer"></i>5.-95. Perzentil</span>
		<span><i class="inner"></i>25.-75. Perzentil</span>
		<span><i class="median"></i>Median, 50. Perzentil</span>
		<span><i class="target"></i>Zielbereich</span>
	</div>
</div>

<style>
	.agp-container {
		width: 100%;
		min-width: 0;
		max-width: 100%;
	}

	.agp-svg {
		display: block;
		width: 100%;
		height: auto;
		min-width: 540px;
	}

	.grid-line,
	.vertical-grid {
		stroke: #d7e0e2;
		stroke-width: 0.8;
		stroke-dasharray: 3 3;
	}

	.value-threshold {
		stroke: #6d9e70;
		stroke-width: 1.2;
		stroke-dasharray: none;
	}

	.axis-label,
	.unit-label,
	.target-label {
		fill: #506a74;
		font-size: 10px;
	}

	.unit-label {
		font-weight: 700;
	}

	.target-label {
		font-size: 9px;
		fill: #3e7748;
	}

	.agp-summary {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.35rem 0.9rem;
		margin-top: 0.25rem;
		font-size: 0.7rem;
		color: #405c67;
	}

	.agp-summary span {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}

	.agp-summary i {
		display: inline-block;
		width: 0.75rem;
		height: 0.55rem;
		border-radius: 0.1rem;
	}

	.outer {
		background: #f5cf75;
	}

	.inner {
		background: #8fc98b;
	}

	.median {
		height: 0.18rem !important;
		background: #236c4a;
	}

	.target {
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
		.agp-container {
			overflow-x: auto;
		}
	}

	@media print {
		.agp-container {
			overflow: visible !important;
		}

		.agp-svg {
			min-width: 0;
		}

		.agp-container.compact .agp-svg {
			width: auto;
			max-width: 100%;
			height: 65mm;
			margin: 0 auto;
		}

		.agp-summary {
			font-size: 7pt;
		}

		.agp-container.compact .agp-summary {
			margin-top: 0.5mm;
			font-size: 6pt;
		}
	}
</style>
