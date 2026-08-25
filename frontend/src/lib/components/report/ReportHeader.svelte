<script lang="ts">
	import type { ReportPeriod } from '$lib/api/report';

	let { period }: { period: ReportPeriod } = $props();

	const formattedDate = $derived(new Date().toLocaleDateString('de-DE'));
</script>

<div class="report-header">
	<div class="header-top">
		<span class="patient-name">Glukose-Bericht</span>
	</div>
	<div class="header-sub">
		<span>Ausgewählte Daten: {period.start} – {period.end} ({period.num_days} Tage)</span>
		<span>Erstellt: {formattedDate}</span>
	</div>
</div>

<style>
	.report-header {
		margin-bottom: 1.5rem;
		padding-bottom: 0.75rem;
		border-bottom: 3px solid var(--color-primary, #3b82f6);
	}
	.header-top {
		font-size: 1.4rem;
		font-weight: 700;
		margin-bottom: 0.25rem;
	}
	.header-sub {
		display: flex;
		justify-content: space-between;
		font-size: 0.85rem;
		color: var(--color-text-muted, #666);
	}
	@media print {
		.report-header {
			border-bottom-width: 2px;
		}
	}
</style>
