<script lang="ts">
	import type { GlucoseStats } from '$lib/api/report';
	import { formatNumber } from './chart';

	let { stats }: { stats: GlucoseStats } = $props();

	const bands = $derived([
		{
			label: 'Sehr hoch',
			range: '> 250 mg/dL',
			value: stats.time_above_250_percent,
			goal: 'Ziel < 5 %',
			color: '#b42318'
		},
		{
			label: 'Hoch',
			range: '181-250 mg/dL',
			value: stats.time_180_250_percent,
			goal: 'Ziel < 25 %',
			color: '#d99a11'
		},
		{
			label: 'Zielbereich',
			range: '70-180 mg/dL',
			value: stats.time_70_180_percent,
			goal: 'Ziel > 70 %',
			color: '#4f9d57'
		},
		{
			label: 'Niedrig',
			range: '54-69 mg/dL',
			value: stats.time_54_70_percent,
			goal: `Gesamt < 70: ${formatNumber(stats.tir_below)} % · Ziel < 4 %`,
			color: '#e5484d'
		},
		{
			label: 'Sehr niedrig',
			range: '< 54 mg/dL',
			value: stats.time_below_54_percent,
			goal: 'Ziel < 1 %',
			color: '#b42318'
		}
	]);

	const shownBands = $derived(bands.map((band) => ({ ...band, displayedValue: band.value ?? 0 })));
</script>

<div class="stats-layout">
	<section class="stat-panel time-in-range" aria-labelledby="time-in-range-title">
		<div class="panel-heading">
			<h3 id="time-in-range-title">Zeit in Bereichen</h3>
			<span>Ziele für Erwachsene mit Diabetes Typ 1 oder 2</span>
		</div>
		<div class="band-bar" aria-label="Zeit in Glukosebereichen">
			{#each shownBands as band}
				{#if band.displayedValue > 0}
					<div
						class="band-fill"
						style={`width: ${band.displayedValue}%; background: ${band.color}`}
						title={`${band.label}: ${formatNumber(band.value)} %`}
					></div>
				{/if}
			{/each}
		</div>
		<div class="band-list">
			{#each bands as band}
				<div class="band-row">
					<span class="band-swatch" style={`background: ${band.color}`}></span>
					<div>
						<strong>{band.label}</strong>
						<span>{band.range}</span>
					</div>
					<strong class="band-value">{formatNumber(band.value)} %</strong>
					<span class="goal">{band.goal}</span>
				</div>
			{/each}
		</div>
	</section>

	<section class="stat-panel metrics" aria-labelledby="metrics-title">
		<div class="panel-heading">
			<h3 id="metrics-title">Glukose-Metrik</h3>
			<span>Aus dem ausgewählten Zeitraum</span>
		</div>
		<div class="metric-list">
			<div class="metric-row">
				<div>
					<strong>Glukose-Durchschnitt</strong>
					<span>Ziel &lt; 154 mg/dL</span>
				</div>
				<b>{formatNumber(stats.mean)} <small>mg/dL</small></b>
			</div>
			<div class="metric-row gmi-row">
				<div>
					<strong>Glukose-Management-Indikator (GMI)</strong>
					<span>Ziel &lt; 7 % beziehungsweise &lt; 53 mmol/mol</span>
				</div>
				<b
					>{formatNumber(stats.gmi)} % <i>/</i>
					{formatNumber(stats.gmi_mmol_mol, 0)} <small>mmol/mol</small></b
				>
			</div>
			<div class="metric-row">
				<div>
					<strong>Glukosevariabilität</strong>
					<span>Variationskoeffizient, Ziel &lt; 36 %</span>
				</div>
				<b>{formatNumber(stats.cv_percent)} %</b>
			</div>
			<div class="metric-row compact-row">
				<div>
					<strong>Datenabdeckung</strong>
					<span>{stats.readings} auswertbare Glukosewerte</span>
				</div>
				<b>{formatNumber(stats.data_coverage_percent)} %</b>
			</div>
		</div>
	</section>
</div>

<style>
	.stats-layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 0.7rem;
	}

	.stat-panel {
		border: 1px solid #b8c6ca;
		border-radius: 0.5rem;
		overflow: hidden;
		background: #fff;
	}

	.panel-heading {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
		align-items: baseline;
		padding: 0.55rem 0.7rem;
		border-bottom: 1px solid #d6dfe2;
	}

	.panel-heading h3 {
		margin: 0;
		font-size: 0.91rem;
		color: #18313d;
	}

	.panel-heading span {
		font-size: 0.65rem;
		text-align: right;
		color: #55707c;
	}

	.band-bar {
		display: flex;
		height: 0.9rem;
		margin: 0.7rem 0.7rem 0.5rem;
		border-radius: 99px;
		overflow: hidden;
		background: #e8eef0;
	}

	.band-fill {
		min-width: 0;
	}

	.band-list {
		padding: 0 0.7rem 0.55rem;
	}

	.band-row {
		display: grid;
		grid-template-columns: 0.55rem minmax(0, 1fr) auto minmax(5.2rem, auto);
		gap: 0.38rem;
		align-items: center;
		padding: 0.22rem 0;
		font-size: 0.67rem;
		border-top: 1px solid #edf1f2;
	}

	.band-row:first-child {
		border-top: 0;
	}

	.band-swatch {
		display: block;
		width: 0.48rem;
		height: 1.05rem;
		border-radius: 0.12rem;
	}

	.band-row div {
		display: grid;
		gap: 0.02rem;
	}

	.band-row div span,
	.metric-row span {
		color: #58707a;
	}

	.band-value {
		font-size: 0.76rem;
		font-variant-numeric: tabular-nums;
		color: #18313d;
	}

	.goal {
		border-radius: 0.2rem;
		padding: 0.12rem 0.22rem;
		background: #edf2f3;
		font-size: 0.61rem;
		color: #405c67;
	}

	.metric-list {
		display: grid;
	}

	.metric-row {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		align-items: center;
		min-height: 2.7rem;
		padding: 0.42rem 0.7rem;
		border-top: 1px solid #dfe7e9;
	}

	.metric-row:first-child {
		border-top: 0;
	}

	.metric-row div {
		display: grid;
		gap: 0.1rem;
	}

	.metric-row strong {
		font-size: 0.72rem;
	}

	.metric-row span {
		font-size: 0.64rem;
	}

	.metric-row b {
		white-space: nowrap;
		font-size: 1rem;
		font-variant-numeric: tabular-nums;
		color: #176b87;
	}

	.metric-row small {
		font-size: 0.62em;
		color: #405c67;
	}

	.metric-row i {
		font-style: normal;
		color: #9aacb2;
	}

	.gmi-row b {
		font-size: 0.88rem;
	}

	.compact-row {
		background: #f3f7f7;
	}

	@media (max-width: 720px) {
		.stats-layout {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 420px) {
		.band-row {
			grid-template-columns: 0.55rem minmax(0, 1fr) auto;
		}

		.goal {
			grid-column: 2 / -1;
			justify-self: start;
		}

		.metric-row {
			align-items: flex-end;
		}
	}

	@media print {
		.stats-layout {
			grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) !important;
			gap: 3mm;
		}

		.panel-heading {
			padding: 2mm 2.5mm;
		}

		.band-bar {
			margin: 2mm 2.5mm 1.5mm;
		}

		.band-list {
			padding: 0 2.5mm 2mm;
		}

		.metric-row {
			min-height: 11mm;
			padding: 1.5mm 2.5mm;
		}
	}
</style>
