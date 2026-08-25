<script lang="ts">
	import type { DailyPatternPoint } from '$lib/api/report';

	let { points }: { points: DailyPatternPoint[] } = $props();

	const width = 800;
	const height = 350;
	const pad = { top: 20, right: 20, bottom: 60, left: 50 };
	const chartW = width - pad.left - pad.right;
	const chartH = height - pad.top - pad.bottom;
	const barAreaH = 60;
	const glucoseH = chartH - barAreaH - 10;

	const Y_MIN = 0;
	const Y_MAX = 350;

	function xScale(i: number): number {
		return pad.left + (i / (points.length - 1 || 1)) * chartW;
	}
	function yScale(v: number): number {
		return pad.top + glucoseH - ((v - Y_MIN) / (Y_MAX - Y_MIN)) * glucoseH;
	}

	function pathD(accessor: (p: DailyPatternPoint) => number | null): string {
		let d = '';
		let started = false;
		for (let i = 0; i < points.length; i++) {
			const v = accessor(points[i]);
			if (v === null) continue;
			const x = xScale(i);
			const y = yScale(v);
			if (!started) {
				d += `M${x},${y}`;
				started = true;
			} else {
				d += `L${x},${y}`;
			}
		}
		return d;
	}

	function areaD(lower: (p: DailyPatternPoint) => number | null, upper: (p: DailyPatternPoint) => number | null): string {
		const fwd: string[] = [];
		const bwd: string[] = [];
		for (let i = 0; i < points.length; i++) {
			const lo = lower(points[i]);
			const hi = upper(points[i]);
			if (lo !== null && hi !== null) {
				fwd.push(`${xScale(i)},${yScale(lo)}`);
				bwd.unshift(`${xScale(i)},${yScale(hi)}`);
			}
		}
		if (fwd.length < 2) return '';
		return `M${fwd.join('L')}L${bwd.join('L')}Z`;
	}

	const maxCarbs = $derived(Math.max(1, ...points.map((p) => p.carbs_avg ?? 0)));
	const maxInsulin = $derived(Math.max(1, ...points.map((p) => p.insulin_avg ?? 0)));

	const tickLabels = $derived(
		points
			.filter((_, i) => i % 6 === 0)
			.map((p) => ({ x: xScale(points.indexOf(p)), label: p.time_label }))
	);
</script>

<div class="pattern-container">
	<svg viewBox="0 0 {width} {height}" class="pattern-svg">
		<!-- Target range -->
		<rect x={pad.left} y={yScale(180)} width={chartW} height={yScale(70) - yScale(180)}
			fill="#dcfce7" opacity="0.4" />

		<!-- Grid -->
		{#each [0, 70, 180, 250, 350] as y}
			<line x1={pad.left} y1={yScale(y)} x2={pad.left + chartW} y2={yScale(y)}
				stroke="#e5e7eb" stroke-width="0.5" />
			<text x={pad.left - 5} y={yScale(y) + 4} text-anchor="end" class="axis-label">{y}</text>
		{/each}

		<!-- 5-95 area -->
		<path d={areaD((p) => p.p5, (p) => p.p95)} fill="#93c5fd" opacity="0.3" />
		<!-- 25-75 area -->
		<path d={areaD((p) => p.p25, (p) => p.p75)} fill="#3b82f6" opacity="0.3" />
		<!-- Median -->
		<path d={pathD((p) => p.p50)} fill="none" stroke="#1d4ed8" stroke-width="2.5" />

		<!-- Carb bars -->
		{#each points as pt, i}
			{#if pt.carbs_avg !== null}
				<rect
					x={xScale(i) - 3}
					y={pad.top + glucoseH + 10 + barAreaH - (pt.carbs_avg / maxCarbs) * barAreaH * 0.5}
					width={6}
					height={(pt.carbs_avg / maxCarbs) * barAreaH * 0.5}
					fill="#22c55e"
					opacity="0.7"
					rx="1"
				/>
			{/if}
			{#if pt.insulin_avg !== null}
				<rect
					x={xScale(i) + 3}
					y={pad.top + glucoseH + 10 + barAreaH - (pt.insulin_avg / maxInsulin) * barAreaH * 0.5}
					width={6}
					height={(pt.insulin_avg / maxInsulin) * barAreaH * 0.5}
					fill="#f97316"
					opacity="0.7"
					rx="1"
				/>
			{/if}
		{/each}

		<!-- X axis -->
		{#each tickLabels as tick}
			<text x={tick.x} y={height - 15} text-anchor="middle" class="axis-label">
				{tick.label}
			</text>
		{/each}
	</svg>

	<div class="legend">
		<span class="legend-item"><span class="swatch" style="background: #93c5fd"></span> 5.–95. Perzentil</span>
		<span class="legend-item"><span class="swatch" style="background: #3b82f6"></span> 25.–75. Perzentil</span>
		<span class="legend-item"><span class="swatch line" style="background: #1d4ed8"></span> Median</span>
		<span class="legend-item"><span class="swatch" style="background: #22c55e"></span> KH (g/Tag)</span>
		<span class="legend-item"><span class="swatch" style="background: #f97316"></span> Insulin (E/Tag)</span>
	</div>
</div>

<style>
	.pattern-container {
		width: 100%;
		overflow-x: auto;
	}
	.pattern-svg {
		width: 100%;
		height: auto;
		max-height: 350px;
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
		flex-wrap: wrap;
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
