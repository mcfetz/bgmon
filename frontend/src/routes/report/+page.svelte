<script lang="ts">
	import { onMount } from 'svelte';
	import ReportView from '$lib/components/report/ReportView.svelte';
	import { fetchReport, type ReportData } from '$lib/api/report';

	let start = $state<string>(
		new Date(Date.now() - 13 * 86400000).toISOString().slice(0, 10)
	);
	let end = $state<string>(new Date().toISOString().slice(0, 10));
	let report = $state<ReportData | null>(null);
	let loading = $state(false);
	let error = $state<string | null>(null);

	async function loadReport() {
		loading = true;
		error = null;
		try {
			report = await fetchReport(start, end);
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	}

	function handlePrint() {
		window.print();
	}

	onMount(() => {
		loadReport();
	});
</script>

<svelte:head>
	<title>AGP-Bericht — bgmon</title>
</svelte:head>

<div class="report-page no-print">
	<div class="report-controls">
		<h1>AGP-Bericht</h1>
		<div class="date-controls">
			<label>
				Von
				<input type="date" bind:value={start} />
			</label>
			<label>
				Bis
				<input type="date" bind:value={end} />
			</label>
			<button class="btn-primary" onclick={loadReport} disabled={loading}>
				{loading ? 'Lade...' : 'Bericht erstellen'}
			</button>
		</div>
	</div>

	{#if error}
		<div class="error">{error}</div>
	{/if}
</div>

{#if report}
	<div class="report-print-controls no-print">
		<button class="btn-print" onclick={handlePrint}>Drucken / PDF</button>
	</div>
	<ReportView {report} />
{:else if !loading && !error}
	<div class="empty">Keine Daten für diesen Zeitraum.</div>
{/if}

<style>
	.report-page {
		padding: 1rem;
		max-width: 1200px;
		margin: 0 auto;
	}

	.report-controls {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	h1 {
		font-size: 1.5rem;
		margin: 0;
	}

	.date-controls {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.date-controls label {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.9rem;
	}

	.date-controls input[type='date'] {
		padding: 0.4rem;
		border: 1px solid var(--color-border, #ccc);
		border-radius: 4px;
		background: var(--color-surface, #fff);
		color: var(--color-text, #000);
	}

	.btn-primary {
		padding: 0.5rem 1rem;
		background: var(--color-primary, #3b82f6);
		color: white;
		border: none;
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.9rem;
	}

	.btn-primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-print {
		padding: 0.5rem 1.5rem;
		background: var(--color-primary, #3b82f6);
		color: white;
		border: none;
		border-radius: 6px;
		cursor: pointer;
		font-size: 1rem;
		font-weight: 600;
	}

	.report-print-controls {
		padding: 0.5rem 1rem;
		text-align: right;
		max-width: 1200px;
		margin: 0 auto;
	}

	.error {
		padding: 0.75rem;
		background: #fee2e2;
		color: #991b1b;
		border-radius: 6px;
		margin-bottom: 1rem;
	}

	.empty {
		text-align: center;
		padding: 3rem;
		color: var(--color-text-muted, #888);
	}

	@media print {
		.report-page,
		.report-print-controls {
			display: none !important;
		}
	}
</style>
