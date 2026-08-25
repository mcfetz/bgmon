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
	const HIGH = 180;

	function xScale(minutes: number): number {
		return pad.left + (minutes / (24 * 60)) * chartW;
	}
	function yScale(v: number): number {
		return pad.top + chartH - ((v - Y_MIN) / (Y_MAX - Y_MIN)) * chartH;
	}

	// Colors: distinct hues for each day line
	const DAY_COLORS = [
		'#ef4444', '#f97316', '#eab308', '#22c55e', '#14b8a6',
		'#3b82f6', '#8b5cf6', '#ec4899', '#f43f5e', '#06b6d4',
		'#84cc16', '#a855f7', '#6366f1', '#d946ef', '#10b981'
	];

	function pathD(readings: [string, number][]): string {
		let d = '';
		let started = false;
		for (const [time, sgv] of readings) {
			const [h, m] = time.split(':').map(Number);
			const x = xScale(h * 60 + m);
			const y = yScale(sgv);
			if (!started) {
				d += `M${x},${y}`;
				started = true;
			} else {
				d += `L${x},${y}`;
			}
		}
		return d;
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

		<!-- Day lines -->
		{#each profiles as profile, i}
			{#if profile.readings.length > 1}
				<path
					d={pathD(profile.readings)}
					fill="none"
					stroke={DAY_COLORS[i % DAY_COLORS.length]}
					stroke-width="1.2"
					opacity="0.6"
				/>
			{/if}
		{/each}

		<!-- X axis labels -->
		{#each tickLabels as tick}
			<text x={tick.x} y={height - 8} text-anchor="middle" class="axis-label">
				{tick.label}
			</text>
		{/each}
	</svg>

	<div class="legend">
		{#each profiles as profile, i}
			<span class="legend-item">
				<span class="swatch" style="background: {DAY_COLORS[i % DAY_COLORS.length]}"></span>
				{profile.weekday} {profile.date.slice(8)}.{profile.date.slice(5, 7)}
			</span>
		{/each}
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
