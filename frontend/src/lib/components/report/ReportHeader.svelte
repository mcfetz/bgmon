<script lang="ts">
	import type { ReportData } from '$lib/api/report';
	import { formatNumber } from './chart';

	let {
		report,
		title,
		pageNote = null,
		pageNumber = null,
		pageTotal = null
	}: {
		report: ReportData;
		title: string;
		pageNote?: string | null;
		pageNumber?: number | null;
		pageTotal?: number | null;
	} = $props();

	const monthNames = [
		'Januar',
		'Februar',
		'März',
		'April',
		'Mai',
		'Juni',
		'Juli',
		'August',
		'September',
		'Oktober',
		'November',
		'Dezember'
	];

	function formatDate(date: string): string {
		const [year, month, day] = date.split('-').map(Number);
		return `${day}. ${monthNames[month - 1]} ${year}`;
	}

	function formatGenerated(timestamp: string, timezone: string): string {
		const date = new Date(timestamp);
		if (Number.isNaN(date.getTime())) return timestamp;
		return new Intl.DateTimeFormat('de-DE', {
			dateStyle: 'medium',
			timeStyle: 'short',
			timeZone: timezone
		}).format(date);
	}

	const generatedLabel = $derived(formatGenerated(report.generated_at, report.timezone));
	const coverageLabel = $derived(formatNumber(report.glucose_stats.data_coverage_percent));
</script>

<header class="report-header">
	<div class="header-topline">
		<div class="brand" aria-label="bgmon">
			<span class="brand-mark">bg</span><span>mon</span>
		</div>
		<span class="report-kind">Glukosebericht</span>
	</div>
	<div class="header-main">
		<div class="patient-block">
			<p class="patient-label">Patient:in</p>
			<p class="patient-name">{report.patient_name || 'Nicht angegeben'}</p>
		</div>
		<div class="title-block">
			<h1>{title}</h1>
			{#if pageNote}
				<p>{pageNote}</p>
			{/if}
		</div>
	</div>
	<div class="header-meta">
		<span
			><strong>{report.period.num_days} Tage</strong>
			{formatDate(report.period.start)} bis {formatDate(report.period.end)}</span
		>
		<span>Datenabdeckung <strong>{coverageLabel} %</strong></span>
		<span>Zeitzone {report.timezone}</span>
		<span>Erstellt {generatedLabel}</span>
	</div>
	{#if pageNumber !== null && pageTotal !== null}
		<div class="page-footer">
			<span>bgmon Glukosebericht</span>
			<span>Seite {pageNumber} / {pageTotal}</span>
		</div>
	{/if}
</header>

<style>
	.report-header {
		border-bottom: 2px solid #176b87;
		padding-bottom: 0.55rem;
		margin-bottom: 0.85rem;
		color: #18313d;
	}

	.header-topline,
	.header-main,
	.header-meta {
		display: flex;
		align-items: center;
	}

	.header-topline {
		justify-content: flex-end;
		gap: 0.45rem;
		font-size: 0.68rem;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: #55707c;
	}

	.brand {
		font-weight: 800;
		font-size: 1.02rem;
		letter-spacing: -0.06em;
		color: #18313d;
		text-transform: none;
	}

	.brand-mark {
		color: #176b87;
	}

	.header-main {
		justify-content: space-between;
		gap: 1rem;
		margin-top: 0.3rem;
		min-width: 0;
		max-width: 100%;
	}

	.header-main > * {
		min-width: 0;
	}

	.patient-block {
		flex: 1 1 0;
		max-width: 36rem;
	}

	.patient-label,
	.patient-name,
	.title-block p {
		margin: 0;
	}

	.patient-label {
		font-size: 0.66rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: #55707c;
	}

	.patient-name {
		min-width: 0;
		max-width: 100%;
		font-size: 1.05rem;
		font-weight: 700;
		overflow-wrap: anywhere;
	}

	.title-block {
		flex: 0 1 auto;
		max-width: 48%;
		text-align: right;
	}

	h1 {
		margin: 0;
		font-size: clamp(1.15rem, 2.5vw, 1.65rem);
		line-height: 1.1;
		color: #176b87;
	}

	.title-block p {
		margin-top: 0.12rem;
		font-size: 0.72rem;
		color: #55707c;
	}

	.header-meta {
		flex-wrap: wrap;
		gap: 0.2rem 0.9rem;
		margin-top: 0.52rem;
		font-size: 0.69rem;
		color: #405c67;
	}

	.page-footer {
		display: flex;
		justify-content: space-between;
		gap: 0.6rem;
		margin-top: 0.46rem;
		padding-top: 0.28rem;
		border-top: 1px solid #d6e0e2;
		font-size: 0.61rem;
		color: #58707a;
	}

	@media (max-width: 560px) {
		.header-main {
			align-items: flex-start;
			flex-direction: column;
		}

		.title-block {
			width: 100%;
			max-width: 100%;
			text-align: left;
		}

		.patient-block {
			width: 100%;
			max-width: 100%;
		}
	}

	@media print {
		.report-header {
			margin-bottom: 4mm;
			padding-bottom: 2mm;
		}

		.header-topline {
			font-size: 7pt;
		}

		.patient-name {
			font-size: 11pt;
		}

		h1 {
			font-size: 16pt;
		}

		.header-meta {
			font-size: 7pt;
		}

		.page-footer {
			margin-top: 1.6mm;
			padding-top: 1mm;
			font-size: 6.2pt;
		}
	}
</style>
