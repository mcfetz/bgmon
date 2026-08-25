<script lang="ts">
	import type { DayOverview } from '$lib/api/report';

	let { days }: { days: DayOverview[] } = $props();

	function sgvColor(sgv: number | null): string {
		if (sgv === null) return '';
		if (sgv < 54) return 'critical-low';
		if (sgv < 70) return 'low';
		if (sgv <= 180) return 'in-range';
		if (sgv <= 250) return 'high';
		return 'critical-high';
	}

	// Monday=1 .. Sunday=7 → grid column 1..7
	function weekdayCol(date: string): number {
		const d = new Date(date + 'T12:00:00');
		const jsDay = d.getDay(); // 0=Sun
		return jsDay === 0 ? 7 : jsDay; // shift so Mon=1
	}
</script>

<div class="calendar-grid">
	<div class="cal-header-row">
		<span>Mo</span><span>Di</span><span>Mi</span><span>Do</span><span>Fr</span><span>Sa</span><span>So</span>
	</div>
	<div class="cal-body">
		{#each days as day}
			<div class="cal-cell" style="grid-column: {weekdayCol(day.date)}">
				<div class="cal-date">{parseInt(day.date.slice(8))}</div>
				{#if day.avg_sgv !== null}
					<div class="cal-avg {sgvColor(day.avg_sgv)}">{day.avg_sgv}</div>
				{/if}
				<div class="cal-meta">
					{#if day.carbs_grams !== null}
						<span title="KH">{day.carbs_grams}g</span>
					{/if}
					{#if day.insulin_units !== null}
						<span title="Insulin">{day.insulin_units}U</span>
					{/if}
					{#if day.hypo_events > 0}
						<span class="hypo" title="Hypo">{day.hypo_events}</span>
					{/if}
				</div>
			</div>
		{/each}
	</div>
</div>

<style>
	.calendar-grid {
		width: 100%;
	}
	.cal-header-row {
		display: grid;
		grid-template-columns: repeat(7, 1fr);
		gap: 2px;
		margin-bottom: 2px;
	}
	.cal-header-row span {
		text-align: center;
		font-size: 0.75rem;
		font-weight: 600;
		padding: 0.3rem;
		color: var(--color-text-muted, #666);
	}
	.cal-body {
		display: grid;
		grid-template-columns: repeat(7, 1fr);
		gap: 2px;
	}
	.cal-cell {
		border: 1px solid var(--color-border, #e5e7eb);
		border-radius: 4px;
		padding: 0.25rem;
		min-height: 50px;
		text-align: center;
		background: var(--color-surface, #fff);
	}
	.cal-date {
		font-size: 0.8rem;
		font-weight: 700;
		margin-bottom: 0.15rem;
	}
	.cal-avg {
		font-size: 0.7rem;
		font-weight: 600;
		padding: 1px 4px;
		border-radius: 3px;
		display: inline-block;
	}
	.cal-meta {
		font-size: 0.6rem;
		color: var(--color-text-muted, #666);
		display: flex;
		justify-content: center;
		gap: 0.3rem;
		margin-top: 0.15rem;
	}
	.hypo {
		color: #dc2626;
		font-weight: 700;
	}
	.critical-low { background: #fecaca; color: #991b1b; }
	.low { background: #fed7aa; color: #9a3412; }
	.in-range { background: #dcfce7; color: #166534; }
	.high { background: #fef08a; color: #854d0e; }
	.critical-high { background: #fecaca; color: #991b1b; }
</style>
