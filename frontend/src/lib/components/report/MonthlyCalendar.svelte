<script lang="ts">
	import type { DayOverview } from '$lib/api/report';
	import { formatNumber } from './chart';

	let { days }: { days: DayOverview[] } = $props();

	function parts(date: string): [number, number, number] {
		const [year, month, day] = date.split('-').map(Number);
		return [year, month, day];
	}

	function weekdayOffset(date: string): number {
		const [year, month, day] = parts(date);
		return (new Date(Date.UTC(year, month - 1, day)).getUTCDay() + 6) % 7;
	}

	interface CalendarSlot {
		day: DayOverview | null;
	}

	function calendarSlots(days: DayOverview[]): CalendarSlot[] {
		const firstSelectedDay = days[0];
		if (!firstSelectedDay) return [];

		return [
			...Array.from({ length: weekdayOffset(firstSelectedDay.date) }, () => ({ day: null })),
			...days.map((day) => ({ day }))
		];
	}

	function cellClass(value: number | null): string {
		if (value === null) return 'no-glucose';
		if (value < 54 || value > 250) return 'critical';
		if (value < 70) return 'low';
		if (value <= 180) return 'in-range';
		return 'high';
	}

	const slots = $derived(calendarSlots(days));
	const gridRows = $derived(Math.max(1, Math.ceil(slots.length / 7)));
</script>

<div class="calendar-scroll">
	<div class="calendar" style={`--calendar-rows: ${gridRows}`}>
		<div class="weekdays" aria-hidden="true">
			<span>Mo</span><span>Di</span><span>Mi</span><span>Do</span><span>Fr</span><span>Sa</span
			><span>So</span>
		</div>
		<div class="calendar-grid" style={`grid-template-rows: repeat(${gridRows}, minmax(74px, 1fr))`}>
			{#each slots as slot}
				{#if slot.day}
					<article class="calendar-cell" class:selected-no-data={slot.day.avg_sgv === null}>
						<div class="date-number">{Number(slot.day.date.slice(8))}</div>
						{#if slot.day.avg_sgv !== null}
							<strong class={`average ${cellClass(slot.day.avg_sgv)}`}
								>{formatNumber(slot.day.avg_sgv, 0)} <small>mg/dL</small></strong
							>
						{:else}
							<span class="no-data">Keine Glukosedaten</span>
						{/if}
						<div class="cell-meta">
							<span>Abdeckung {formatNumber(slot.day.data_coverage_percent)} %</span>
							<span class:low-events={slot.day.low_events > 0}
								>Niedrige Ereignisse {slot.day.low_events}</span
							>
						</div>
					</article>
				{:else}
					<div class="calendar-placeholder" aria-hidden="true"></div>
				{/if}
			{/each}
		</div>
	</div>
</div>

<style>
	.calendar-scroll {
		width: 100%;
		min-width: 0;
		max-width: 100%;
		overflow-x: auto;
	}

	.calendar {
		min-width: 590px;
	}

	.weekdays,
	.calendar-grid {
		display: grid;
		grid-template-columns: repeat(7, minmax(0, 1fr));
	}

	.weekdays {
		gap: 0.2rem;
		margin-bottom: 0.2rem;
	}

	.weekdays span {
		padding: 0.25rem 0;
		text-align: center;
		font-size: 0.73rem;
		font-weight: 700;
		color: #516b75;
	}

	.calendar-grid {
		gap: 0.2rem;
		min-height: calc(var(--calendar-rows) * 76px);
	}

	.calendar-cell {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		min-height: 74px;
		border: 1px solid #bdcbcf;
		border-radius: 0.25rem;
		padding: 0.35rem;
		background: #fff;
	}

	.calendar-cell.selected-no-data {
		border-style: dashed;
	}

	.calendar-placeholder {
		position: relative;
		min-height: 74px;
		border: 1px solid #e2e9ea;
		border-radius: 0.25rem;
		background: #f6f8f8;
		pointer-events: none;
	}

	.date-number {
		align-self: flex-end;
		margin: -0.35rem -0.35rem 0.18rem 0;
		min-width: 1.45rem;
		padding: 0.12rem 0.22rem;
		border-left: 1px solid #bdcbcf;
		border-bottom: 1px solid #bdcbcf;
		font-size: 0.72rem;
		font-weight: 700;
		text-align: center;
		color: #3f5963;
		background: #f4f7f7;
	}

	.average {
		font-size: 0.92rem;
		font-variant-numeric: tabular-nums;
	}

	.average small {
		font-size: 0.58rem;
		font-weight: 600;
	}

	.average.in-range {
		color: #28713d;
	}

	.average.high {
		color: #a16900;
	}

	.average.low,
	.average.critical {
		color: #b42318;
	}

	.no-data {
		margin-top: 0.2rem;
		font-size: 0.66rem;
		color: #74868d;
	}

	.cell-meta {
		display: grid;
		gap: 0.08rem;
		margin-top: auto;
		padding-top: 0.3rem;
		font-size: 0.61rem;
		color: #58707a;
	}

	.low-events {
		color: #b42318;
		font-weight: 700;
	}

	@media print {
		.calendar-scroll {
			overflow: visible;
		}

		.calendar {
			min-width: 0;
		}

		.weekdays {
			gap: 1.2mm;
			margin-bottom: 1.2mm;
		}

		.calendar-grid {
			gap: 1.2mm;
			min-height: calc(var(--calendar-rows) * 23mm);
		}

		.calendar-cell {
			min-height: 22mm;
			padding: 1.5mm;
		}

		.calendar-placeholder {
			min-height: 22mm;
		}
	}
</style>
