<script lang="ts">
	import type { AGPPoint } from '$lib/api/report';

	let { points }: { points: AGPPoint[] } = $props();

	const width = 800;
	const height = 300;
	const pad = { top: 20, right: 20, bottom: 40, left: 50 };
	const chartW = width - pad.left - pad.right;
	const chartH = height - pad.top - pad.bottom;

	const yMin = 0;
	const yMax = 350;

	function xScale(i: number): number {
		return pad.left + (i / (points.length - 1 || 1)) * chartW;
	}
	function yScale(v: number): number {
		return pad.top + chartH - ((v - yMin) / (yMax - yMin)) * chartH;
	}

	function pathD(values: (number | null)[]): string {
		let d = '';
		let started = false;
		for (let i = 0; i < values.length; i++) {
			if (values[i] === null) continue;
			const x = xScale(i);
			const y = yScale(values[i]!);
			if (!started) {
				d += `M${x},${y}`;
				started = true;
			} else {
				d += `L${x},${y}`;
			}
		}
		return d;
	}

	function areaD(lower: (number | null)[], upper: (number | null)[]): string {
		const forward: string[] = [];
		const backward: string[] = [];
		for (let i = 0; i < lower.length; i++) {
			if (lower[i] !== null && upper[i] !== null) {
				forward.push(`${xScale(i)},${yScale(lower[i]!)}`);
				backward.unshift(`${xScale(i)},${yScale(upper[i]!)}`);
			}
		}
		if (forward.length < 2) return '';
		return `M${forward.join('L')}L${backward.join('L')}Z`;
	}

	const p5 = $derived(points.map((p) => p.p5));
	const p25 = $derived(points.map((p) => p.p25));
	const p50 = $derived(points.map((p) => p.p50));
	const p75 = $derived(points.map((p) => p.p75));
	const p95 = $derived(points.map((p) => p.p95));

	const tickLabels = $derived(
		points
			.filter((_, i) => i % 6 === 0)
			.map((p) => ({ x: xScale(p.bucket_index), label: p.time_label }))
	);
</script>

<div class="agp-container">
	<svg viewBox="0 0 {width} {height}" class="agp-svg">
		<!-- Target range band -->
		<rect
			x={pad.left}
			y={yScale(180)}
			width={chartW}
			height={yScale(70) - yScale(180)}
			fill="#dcfce7"
			opacity="0.5"
		/>

		<!-- Grid lines -->
		{#each [0, 54, 70, 180, 250, 350] as y}
			<line
				x1={pad.left}
				y1={yScale(y)}
				x2={pad.left + chartW}
				y2={yScale(y)}
				stroke="#e5e7eb"
				stroke-width="0.5"
			/>
			<text x={pad.left - 5} y={yScale(y) + 4} text-anchor="end" class="axis-label">
				{y}
			</text>
		{/each}

		<!-- 5-95 area -->
		<path d={areaD(p5, p95)} fill="#93c5fd" opacity="0.3" />

		<!-- 25-75 area -->
		<path d={areaD(p25, p75)} fill="#3b82f6" opacity="0.3" />

		<!-- Median line -->
		<path d={pathD(p50)} fill="none" stroke="#1d4ed8" stroke-width="2.5" />

		<!-- 5th and 95th percentile lines -->
		<path d={pathD(p5)} fill="none" stroke="#93c5fd" stroke-width="1" stroke-dasharray="4,2" />
		<path d={pathD(p95)} fill="none" stroke="#93c5fd" stroke-width="1" stroke-dasharray="4,2" />

		<!-- X axis labels -->
		{#each tickLabels as tick}
			<text x={tick.x} y={height - 8} text-anchor="middle" class="axis-label">
				{tick.label}
			</text>
		{/each}
	</svg>

	<div class="legend">
		<span class="legend-item"><span class="swatch" style="background: #93c5fd"></span> 5.–95. Perzentil</span>
		<span class="legend-item"><span class="swatch" style="background: #3b82f6"></span> 25.–75. Perzentil</span>
		<span class="legend-item"><span class="swatch line" style="background: #1d4ed8"></span> Median (50.)</span>
	</div>
</div>

<style>
	.agp-container {
		width: 100%;
		overflow-x: auto;
	}
	.agp-svg {
		width: 100%;
		height: auto;
		max-height: 300px;
	}
	.axis-label {
		font-size: 10px;
		fill: #666;
	}
	.legend {
		display: flex;
		gap: 1rem;
		justify-content: center;
		margin-top: 0.5rem;
		font-size: 0.8rem;
	}
	.legend-item {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}
	.swatch {
		display: inline-block;
		width: 12px;
		height: 12px;
		border-radius: 2px;
	}
	.swatch.line {
		height: 2px;
		border-radius: 0;
	}
</style>
