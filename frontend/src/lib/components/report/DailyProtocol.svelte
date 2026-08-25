<script lang="ts">
	import type { DayProtocol } from '$lib/api/report';

	let { protocols }: { protocols: DayProtocol[] } = $props();

	function cellClass(val: number | null): string {
		if (val === null) return 'empty';
		if (val < 54) return 'critical-low';
		if (val < 70) return 'low';
		if (val <= 180) return 'in-range';
		if (val <= 250) return 'high';
		return 'critical-high';
	}
</script>

<div class="protocol-scroll">
	<table class="protocol-table">
		<thead>
			<tr>
				<th class="day-col"></th>
				{#each Array.from({ length: 12 }, (_, i) => i) as h}
					<th colspan="2" class="interval-header">{String(h * 2).padStart(2, '0')}:00</th>
				{/each}
			</tr>
			<tr>
				<th></th>
				{#each Array.from({ length: 12 }, (_, i) => i) as _h}
					<th class="sub-col">Min</th>
					<th class="sub-col">Max</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each protocols as proto}
				<tr>
					<td class="day-col">{proto.weekday} {proto.date.slice(8)}.{proto.date.slice(5, 7)}</td>
					{#each proto.intervals as interval}
						<td class="cell {cellClass(interval.min_val)}">
							{interval.min_val ?? '–'}
						</td>
						<td class="cell {cellClass(interval.max_val)}">
							{interval.max_val ?? '–'}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.protocol-scroll {
		overflow-x: auto;
	}
	.protocol-table {
		border-collapse: collapse;
		font-size: 0.65rem;
		width: 100%;
		min-width: 800px;
	}
	.protocol-table th,
	.protocol-table td {
		border: 1px solid var(--color-border, #e5e7eb);
		padding: 2px 3px;
		text-align: center;
		white-space: nowrap;
	}
	.day-col {
		text-align: left !important;
		font-weight: 600;
		font-size: 0.7rem;
		position: sticky;
		left: 0;
		background: var(--color-surface, #fff);
		z-index: 1;
	}
	.interval-header {
		font-size: 0.6rem;
		font-weight: 600;
		background: var(--color-surface-secondary, #f8f9fa);
	}
	.sub-col {
		font-size: 0.55rem;
		color: var(--color-text-muted, #888);
		font-weight: 400;
	}
	.cell {
		font-variant-numeric: tabular-nums;
	}
	.critical-low { background: #fecaca; color: #991b1b; }
	.low { background: #fed7aa; color: #9a3412; }
	.in-range { background: #dcfce7; color: #166534; }
	.high { background: #fef08a; color: #854d0e; }
	.critical-high { background: #fecaca; color: #991b1b; }
	.empty { color: var(--color-text-muted, #ccc); }
</style>
