<script lang="ts">
	import type { WeeklyDay } from '$lib/api/report';

	let { days }: { days: WeeklyDay[] } = $props();

	const chartW = 200;
	const chartH = 50;
	const Y_MIN = 0;
	const Y_MAX = 350;

	function scaleY(v: number): number {
		return chartH - (v / Y_MAX) * chartH;
	}
	function scaleX(minutes: number): number {
		return (minutes / (24 * 60)) * chartW;
	}
</script>

<div class="weekly-grid">
	{#each days as day}
		<div class="week-row">
			<div class="week-label">
				<span class="week-day">{day.weekday}</span>
				<span class="week-date">{day.date.slice(8)}.{day.date.slice(5, 7)}</span>
			</div>
			<div class="week-chart">
				<svg viewBox="0 0 {chartW} {chartH}">
					<!-- Target range -->
					<rect x={0} y={scaleY(180)} width={chartW} height={scaleY(70) - scaleY(180)}
						fill="#dcfce7" opacity="0.3" />
					{#if day.glucose_points.length > 1}
						<polyline
							points={day.glucose_points
								.map(([time, sgv]) => {
									const [h, m] = time.split(':').map(Number);
									return `${scaleX(h * 60 + m)},${scaleY(sgv)}`;
								})
								.join(' ')}
							fill="none" stroke="#1d4ed8" stroke-width="1" />
					{/if}
				</svg>
			</div>
			<div class="week-meta">
				<span class="meta-avg">{day.avg_sgv ?? '–'} mg/dL</span>
				{#if day.carbs_grams !== null}
					<span class="meta-carbs">🍞 {day.carbs_grams}g</span>
				{/if}
				{#if day.insulin_units !== null}
					<span class="meta-insulin">💉 {day.insulin_units}U</span>
				{/if}
				{#if day.hypo_events > 0}
					<span class="meta-hypo">⚠ {day.hypo_events}</span>
				{/if}
			</div>
		</div>
	{/each}
</div>

<style>
	.weekly-grid {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.week-row {
		display: grid;
		grid-template-columns: 70px 1fr auto;
		gap: 0.5rem;
		align-items: center;
		padding: 0.25rem 0;
		border-bottom: 1px solid var(--color-border, #f0f0f0);
	}
	.week-label {
		display: flex;
		flex-direction: column;
		font-size: 0.75rem;
	}
	.week-day {
		font-weight: 700;
	}
	.week-date {
		color: var(--color-text-muted, #666);
		font-size: 0.65rem;
	}
	.week-chart svg {
		width: 100%;
		height: auto;
		max-height: 50px;
	}
	.week-meta {
		display: flex;
		gap: 0.5rem;
		font-size: 0.7rem;
		align-items: center;
	}
	.meta-avg {
		font-weight: 600;
		min-width: 65px;
		text-align: right;
	}
	.meta-hypo {
		color: #dc2626;
		font-weight: 600;
	}
</style>
