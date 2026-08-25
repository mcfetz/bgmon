<script lang="ts">
	import type { MealBlock } from '$lib/api/report';

	let { blocks }: { blocks: MealBlock[] } = $props();

	const blockLabels: Record<string, string> = {
		morning: 'Morgens (04–10)',
		midday: 'Mittags (10–16)',
		evening: 'Abends (16–22)',
		night: 'Nachts (22–04)'
	};
</script>

<div class="meal-grid">
	{#each blocks as block}
		{#if block.points.length > 0}
			<div class="meal-block">
				<h4>{blockLabels[block.name] ?? block.name}</h4>
				<div class="meal-chart">
					<div class="chart-row header-row">
						{#each block.points as pt}
							<div class="chart-col">{pt.offset_label}</div>
						{/each}
					</div>
					<div class="chart-row">
						{#each block.points as pt}
							<div class="chart-col">
								{#if pt.median_sgv !== null}
									<div class="bar-container">
										<div
											class="bar"
											style="height: {Math.min(100, (pt.median_sgv / 350) * 100)}%"
										></div>
									</div>
									<div class="bar-value">{pt.median_sgv}</div>
								{:else}
									<div class="no-data">–</div>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			</div>
		{/if}
	{/each}
</div>

<style>
	.meal-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 1rem;
	}
	.meal-block h4 {
		font-size: 0.85rem;
		margin: 0 0 0.5rem 0;
	}
	.meal-chart {
		text-align: center;
	}
	.chart-row {
		display: flex;
		gap: 0.5rem;
		justify-content: center;
	}
	.header-row {
		margin-bottom: 0.25rem;
	}
	.chart-col {
		flex: 1;
		max-width: 60px;
		font-size: 0.7rem;
	}
	.header-row .chart-col {
		font-weight: 600;
		color: var(--color-text-muted, #666);
	}
	.bar-container {
		height: 80px;
		display: flex;
		align-items: flex-end;
		justify-content: center;
	}
	.bar {
		width: 70%;
		background: var(--color-primary, #3b82f6);
		border-radius: 3px 3px 0 0;
		min-height: 2px;
	}
	.bar-value {
		font-size: 0.7rem;
		margin-top: 0.15rem;
		font-weight: 600;
	}
	.no-data {
		color: var(--color-text-muted, #ccc);
		padding-top: 2rem;
	}
</style>
