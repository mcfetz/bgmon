<script lang="ts">
	import type { MealBlock, MealPoint } from '$lib/api/report';
	import { areaPaths, clampGlucose, glucoseRangeCapMarkers, linePath } from './chart';

	let { blocks }: { blocks: MealBlock[] } = $props();

	const blockDefinitions = [
		{ name: 'morning', label: 'Morgens', hours: '04:00 - 10:00' },
		{ name: 'midday', label: 'Mittags', hours: '10:00 - 16:00' },
		{ name: 'evening', label: 'Abends', hours: '16:00 - 22:00' },
		{ name: 'night', label: 'Nachts', hours: '22:00 - 04:00' }
	];
	const width = 260;
	const height = 210;
	const pad = { top: 16, right: 12, bottom: 36, left: 31 };
	const chartWidth = width - pad.left - pad.right;
	const chartHeight = height - pad.top - pad.bottom;

	const displayBlocks = $derived(
		blockDefinitions.map((definition) => ({
			...definition,
			block: blocks.find((block) => block.name === definition.name) ?? {
				name: definition.name,
				hours_label: definition.hours,
				points: []
			}
		}))
	);

	function xScale(index: number, count: number): number {
		return pad.left + (index / Math.max(count - 1, 1)) * chartWidth;
	}

	function yScale(value: number): number {
		return pad.top + chartHeight - (clampGlucose(value) / 350) * chartHeight;
	}

	function values(points: MealPoint[], key: 'p25' | 'median_sgv' | 'p75'): (number | null)[] {
		return points.map((point) => point[key]);
	}

	function quartileAreas(points: MealPoint[]): string[] {
		return areaPaths(
			values(points, 'p25'),
			values(points, 'p75'),
			(index) => xScale(index, points.length),
			yScale
		);
	}

	function medianPath(points: MealPoint[]): string {
		return linePath(values(points, 'median_sgv'), (index) => xScale(index, points.length), yScale);
	}

	function glucoseCaps(points: MealPoint[]) {
		return glucoseRangeCapMarkers(
			[values(points, 'p25'), values(points, 'median_sgv'), values(points, 'p75')],
			(index) => xScale(index, points.length),
			yScale
		);
	}

	function hasValues(points: MealPoint[]): boolean {
		return points.some((point) => point.median_sgv !== null);
	}
</script>

<div class="meal-grid">
	{#each displayBlocks as item}
		{@const caps = glucoseCaps(item.block.points)}
		<article class="meal-panel">
			<header>
				<strong>{item.label}</strong>
				<span>{item.block.hours_label || item.hours}</span>
			</header>
			{#if item.block.points.length === 0}
				<div class="empty-meal">Keine protokollierten Kohlenhydrate in diesem Zeitfenster.</div>
			{:else}
				<svg
					viewBox={`0 0 ${width} ${height}`}
					class="meal-chart"
					role="img"
					aria-label={`Mahlzeitenprofil ${item.label}`}
				>
					<rect
						x={pad.left}
						y={yScale(180)}
						width={chartWidth}
						height={yScale(70) - yScale(180)}
						fill="#dcefdc"
					/>
					{#each [0, 70, 180, 350] as value}
						<line
							x1={pad.left}
							y1={yScale(value)}
							x2={pad.left + chartWidth}
							y2={yScale(value)}
							class:target={value === 70 || value === 180}
							class="grid"
						/>
						<text x={pad.left - 5} y={yScale(value) + 3} text-anchor="end" class="axis"
							>{value}</text
						>
					{/each}
					{#each item.block.points as point, index}
						<line
							x1={xScale(index, item.block.points.length)}
							y1={pad.top}
							x2={xScale(index, item.block.points.length)}
							y2={pad.top + chartHeight}
							class="vertical"
						/>
						<text
							x={xScale(index, item.block.points.length)}
							y={height - 9}
							text-anchor="middle"
							class="axis">{point.offset_label}</text
						>
					{/each}
					{#each quartileAreas(item.block.points) as path}<path
							d={path}
							fill="#8fc98b"
							opacity="0.65"
						/>{/each}
					<path d={medianPath(item.block.points)} fill="none" stroke="#236c4a" stroke-width="2.2" />
					{#each item.block.points as point, index}
						{#if point.median_sgv !== null}
							<circle
								cx={xScale(index, item.block.points.length)}
								cy={yScale(point.median_sgv)}
								r="3"
								fill="#236c4a"
							/>
						{/if}
					{/each}
					{#each caps as cap}
						<path d={cap.d} fill={cap.color} stroke="#fff" stroke-width="0.8">
							<title>{cap.label}</title>
						</path>
					{/each}
				</svg>
				{#if !hasValues(item.block.points)}
					<p class="empty-meal chart-message">
						Keine passenden Glukosewerte zu den protokollierten Kohlenhydraten.
					</p>
				{/if}
			{/if}
		</article>
	{/each}
</div>

<div class="meal-legend">
	<span><i class="quartile"></i>25.-75. Perzentil</span>
	<span><i class="median"></i>Median</span>
	<span><i class="target"></i>Zielbereich 70-180 mg/dL</span>
	<span>Bezugszeit: -1 h, +1 h, +2 h und +3 h zur protokollierten Kohlenhydratmenge.</span>
</div>

<style>
	.meal-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.55rem;
	}

	.meal-panel {
		display: flex;
		flex-direction: column;
		min-width: 0;
		min-height: 12.8rem;
		border: 1px solid #bdcbcf;
		border-radius: 0.4rem;
		padding: 0.45rem;
		background: #fff;
	}

	.meal-panel header {
		margin-bottom: 0.15rem;
	}

	.meal-panel header strong,
	.meal-panel header span {
		display: block;
	}

	.meal-panel header strong {
		font-size: 0.78rem;
		color: #18313d;
	}

	.meal-panel header span {
		font-size: 0.63rem;
		color: #58707a;
	}

	.meal-chart {
		display: block;
		width: 100%;
		height: auto;
	}

	.grid,
	.vertical {
		stroke: #d7e0e2;
		stroke-width: 0.7;
		stroke-dasharray: 2 2;
	}

	.grid.target {
		stroke: #73a373;
		stroke-width: 1;
		stroke-dasharray: none;
	}

	.axis {
		font-size: 8px;
		fill: #607982;
	}

	.empty-meal {
		display: grid;
		place-items: center;
		flex: 1;
		min-height: 8rem;
		margin: 0;
		padding: 0.7rem;
		text-align: center;
		font-size: 0.72rem;
		color: #687d85;
		background: repeating-linear-gradient(-45deg, #f7f9f9, #f7f9f9 5px, #f1f5f5 5px, #f1f5f5 10px);
	}

	.chart-message {
		min-height: 0;
		margin-top: 0.1rem;
		background: transparent;
	}

	.meal-legend {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.3rem 0.8rem;
		margin-top: 0.42rem;
		font-size: 0.66rem;
		color: #536b75;
	}

	.meal-legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.22rem;
	}

	.meal-legend i {
		display: inline-block;
		width: 0.75rem;
		height: 0.55rem;
		border-radius: 0.1rem;
	}

	.quartile {
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

	@media (max-width: 820px) {
		.meal-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 500px) {
		.meal-grid {
			grid-template-columns: 1fr;
		}
	}

	@media print {
		.meal-grid {
			grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
			gap: 2.5mm;
		}

		.meal-panel {
			min-height: 51mm;
			padding: 1.6mm;
		}

		.meal-legend {
			font-size: 6pt;
		}
	}
</style>
