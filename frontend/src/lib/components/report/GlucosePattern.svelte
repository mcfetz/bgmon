<script lang="ts">
	import type { DailyProfile } from '$lib/api/report';

	let { profiles }: { profiles: DailyProfile[] } = $props();

	const width = 800;
	const height = 300;
	const pad = { top: 20, right: 20, bottom: 40, left: 50 };
	const chartW = width - pad.left - pad.right;
	const chartH = height - pad.top - pad.bottom;

	const Y_MIN = 0;
	const Y_MAX = 350;

	const LOW = 70;
	const CRITICAL_LOW = 54;
	const HIGH = 180;
	const CRITICAL_HIGH = 250;

	function xScale(minutes: number): number {
		return pad.left + (minutes / (24 * 60)) * chartW;
	}
	function yScale(v: number): number {
		return pad.top + chartH - ((v - Y_MIN) / (Y_MAX - Y_MIN)) * chartH;
	}

	function sgvColor(v: number): string {
		if (v < CRITICAL_LOW) return '#dc2626';
		if (v < LOW) return '#ef4444';
		if (v <= HIGH) return '#22c55e';
		if (v <= CRITICAL_HIGH) return '#eab308';
		return '#ef4444';
	}

	interface Segment {
		d: string;
		color: string;
	}

	function segments(readings: [string, number][]): Segment[] {
		const result: Segment[] = [];
		if (readings.length < 2) return result;

		for (let i = 0; i < readings.length - 1; i++) {
			const [h1, m1] = readings[i][0].split(':').map(Number);
			const [h2, m2] = readings[i + 1][0].split(':').map(Number);
			const x1 = xScale(h1 * 60 + m1);
			const y1 = yScale(readings[i][1]);
			const x2 = xScale(h2 * 60 + m2);
			const y2 = yScale(readings[i + 1][1]);

			// Use the higher of the two values for the segment color
			const color = sgvColor(Math.max(readings[i][1], readings[i + 1][1]));
			result.push({ d: `M${x1},${y1}L${x2},${y2}`, color });
		}
		return result;
	}

	const tickLabels = $derived(
		[0, 3, 6, 9, 12, 15, 18, 21, 24].map((h) => ({
			x: xScale(h * 60),
			label: `${String(h).padStart(2, '0')}:00`
		}))
	);
</script>

<div class="pattern-container">
	<svg viewBox="0 0 {width} {height}" class="pattern-svg">
		<!-- Target range band -->
		<rect
			x={pad.left}
			y={yScale(HIGH)}
			width={chartW}
			height={yScale(LOW) - yScale(HIGH)}
			fill="#dcfce7"
			opacity="0.4"
		/>
		<!-- Grid lines -->
		{#each [0, 54, 70, 180, 250, 350] as y}
			<line
				x1={pad.left} y1={yScale(y)}
				x2={pad.left + chartW} y2={yScale(y)}
				stroke="#e5e7eb" stroke-width="0.5"
			/>
			<text x={pad.left - 5} y={yScale(y) + 4} text-anchor="end" class="axis-label">
				{y}
			</text>
		{/each}

		<!-- Day lines — segments colored by glucose band -->
		{#each profiles as profile}
			{#each segments(profile.readings) as seg}
				<path d={seg.d} fill="none" stroke={seg.color} stroke-width="1.2" opacity="0.7" />
			{/each}
		{/each}

		<!-- X axis labels -->
		{#each tickLabels as tick}
			<text x={tick.x} y={height - 8} text-anchor="middle" class="axis-label">
				{tick.label}
			</text>
		{/each}
	</svg>

	<div class="legend">
		<span class="legend-item"><span class="swatch" style="background: #22c55e"></span> Zielbereich (70–180)</span>
		<span class="legend-item"><span class="swatch" style="background: #eab308"></span> Hoch (180–250)</span>
		<span class="legend-item"><span class="swatch" style="background: #ef4444"></span> Niedrig (&lt;70) / Sehr hoch (&gt;250)</span>
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
		max-height: 320px;
	}
	.axis-label {
		font-size: 10px;
		fill: #666;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
		justify-content: center;
		margin-top: 0.5rem;
		font-size: 0.75rem;
	}
	.legend-item {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}
	.swatch {
		display: inline-block;
		width: 12px;
		height: 3px;
		border-radius: 1px;
	}
</style>
