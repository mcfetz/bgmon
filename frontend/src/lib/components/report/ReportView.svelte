<script lang="ts">
	import type { ReportData } from '$lib/api/report';
	import ReportHeader from './ReportHeader.svelte';
	import GlucoseStatsSection from './GlucoseStatsSection.svelte';
	import AGPCurve from './AGPCurve.svelte';
	import DailyProfiles from './DailyProfiles.svelte';
	import MonthlyCalendar from './MonthlyCalendar.svelte';
	import DailyProtocol from './DailyProtocol.svelte';
	import ReportSnapshot from './ReportSnapshot.svelte';
	import MealProfile from './MealProfile.svelte';
	import WeeklyOverview from './WeeklyOverview.svelte';
	import DailyPattern from './DailyPattern.svelte';

	let { report }: { report: ReportData } = $props();
</script>

<div class="report-container">
	<ReportHeader period={report.period} />

	<section class="report-section">
		<h2>Glukosestatistik und -Ziele</h2>
		<GlucoseStatsSection stats={report.glucose_stats} period={report.period} />
	</section>

	<section class="report-section">
		<h2>Ambulantes Glukoseprofil (AGP)</h2>
		<AGPCurve points={report.agp_curve} />
	</section>

	<section class="report-section">
		<h2>Täglische Glukoseprofile</h2>
		<DailyProfiles profiles={report.daily_profiles} />
	</section>

	{#each getMonthGroups(report.monthly_overview) as month}
		<section class="report-section">
			<h2>Monatsübersicht — {month.label}</h2>
			<MonthlyCalendar days={month.days} />
		</section>
	{/each}

	<section class="report-section">
		<h2>Tagesprotokoll — {report.period.start} bis {report.period.end}</h2>
		<DailyProtocol protocols={report.daily_protocols} />
	</section>

	<section class="report-section">
		<h2>Momentaufnahme</h2>
		<ReportSnapshot snapshot={report.snapshot} period={report.period} />
	</section>

	{#if report.meal_profile.some((b) => b.points.length > 0)}
		<section class="report-section">
			<h2>Mahlzeitenprofil</h2>
			<MealProfile blocks={report.meal_profile} />
		</section>
	{/if}

	<section class="report-section">
		<h2>Wochenübersicht</h2>
		<WeeklyOverview days={report.weekly_overview} />
	</section>

	<section class="report-section">
		<h2>Tagesmuster</h2>
		<DailyPattern points={report.daily_pattern} />
	</section>
</div>

<script module>
	import type { DayOverview } from '$lib/api/report';

	interface MonthGroup {
		label: string;
		days: DayOverview[];
	}

	export function getMonthGroups(days: DayOverview[]): MonthGroup[] {
		const groups: MonthGroup[] = [];
		let currentKey = '';
		let currentLabel = '';
		let currentDays: DayOverview[] = [];
		const monthNames = [
			'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
			'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
		];

		for (const day of days) {
			const d = new Date(day.date + 'T12:00:00');
			const key = `${d.getFullYear()}-${d.getMonth()}`;
			const label = `${monthNames[d.getMonth()]} ${d.getFullYear()}`;
			if (key !== currentKey) {
				if (currentDays.length > 0) groups.push({ label: currentLabel, days: currentDays });
				currentKey = key;
				currentLabel = label;
				currentDays = [];
			}
			currentDays.push(day);
		}
		if (currentDays.length > 0) groups.push({ label: currentLabel, days: currentDays });
		return groups;
	}
</script>

<style>
	.report-container {
		max-width: 1100px;
		margin: 0 auto;
		padding: 1rem;
		background: var(--color-surface, #fff);
	}

	.report-section {
		margin-bottom: 2rem;
		page-break-inside: avoid;
	}

	.report-section h2 {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0 0 0.75rem 0;
		padding-bottom: 0.25rem;
		border-bottom: 2px solid var(--color-primary, #3b82f6);
		color: var(--color-text, #1a1a2e);
	}

	@media print {
		.report-container {
			padding: 0;
			max-width: 100%;
		}
		.report-section {
			page-break-inside: avoid;
		}
	}
</style>
