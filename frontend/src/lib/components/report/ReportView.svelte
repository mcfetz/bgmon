<script lang="ts">
	import type { DayOverview, GlucosePoint, LowGlucoseEvent, ReportData } from '$lib/api/report';
	import ReportHeader from './ReportHeader.svelte';
	import GlucoseStatsSection from './GlucoseStatsSection.svelte';
	import AGPCurve from './AGPCurve.svelte';
	import GlucosePattern from './GlucosePattern.svelte';
	import DailyProfiles from './DailyProfiles.svelte';
	import MonthlyCalendar from './MonthlyCalendar.svelte';
	import DailyProtocol from './DailyProtocol.svelte';
	import ReportSnapshot from './ReportSnapshot.svelte';
	import MealProfile from './MealProfile.svelte';
	import WeeklyOverview from './WeeklyOverview.svelte';
	import DailyPattern from './DailyPattern.svelte';

	let { report }: { report: ReportData } = $props();

	const compactProfiles = $derived(report.daily_profiles.slice(0, 14));
	const readingsByDate = $derived.by(
		(): ReadonlyMap<string, GlucosePoint[]> =>
			new Map(report.daily_profiles.map((profile) => [profile.date, profile.readings] as const))
	);
	const monthGroups = $derived(getMonthGroups(report.monthly_overview));
	const protocolPages = $derived(chunk(report.daily_protocols, 4));
	const snapshotEventPages = $derived(snapshotPages(report.snapshot.low_events));
	const weeklyPages = $derived(chunk(report.weekly_overview, 7));
	const monthPageStart = 3;
	const protocolPageStart = $derived(monthPageStart + monthGroups.length);
	const snapshotPageStart = $derived(protocolPageStart + protocolPages.length);
	const mealPage = $derived(snapshotPageStart + snapshotEventPages.length);
	const weeklyPageStart = $derived(mealPage + 1);
	const dailyPatternPage = $derived(weeklyPageStart + weeklyPages.length);
	const pageTotal = $derived(dailyPatternPage);

	function chunk<T>(items: T[], size: number): T[][] {
		const pages: T[][] = [];
		for (let index = 0; index < items.length; index += size) {
			pages.push(items.slice(index, index + size));
		}
		return pages;
	}

	function snapshotPages(events: LowGlucoseEvent[]): LowGlucoseEvent[][] {
		return [events.slice(0, 10), ...chunk(events.slice(10), 20)];
	}

	interface MonthGroup {
		label: string;
		days: DayOverview[];
	}

	function getMonthGroups(days: DayOverview[]): MonthGroup[] {
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
		const groups: MonthGroup[] = [];
		let key = '';
		let label = '';
		let groupDays: DayOverview[] = [];

		for (const day of days) {
			const [year, month] = day.date.split('-').map(Number);
			const nextKey = `${year}-${month}`;
			if (nextKey !== key) {
				if (groupDays.length > 0) groups.push({ label, days: groupDays });
				key = nextKey;
				label = `${monthNames[month - 1]} ${year}`;
				groupDays = [];
			}
			groupDays.push(day);
		}
		if (groupDays.length > 0) groups.push({ label, days: groupDays });
		return groups;
	}

	function protocolNote(index: number, pageCount: number): string | null {
		return pageCount > 1 ? `Teil ${index + 1} von ${pageCount}` : null;
	}

	function weeklyNote(index: number, pageCount: number): string | null {
		return pageCount > 1 ? `Teil ${index + 1} von ${pageCount}` : null;
	}

	function snapshotNote(index: number, pageCount: number): string | null {
		return pageCount > 1 ? `Niedrige Ereignisse, Teil ${index + 1} von ${pageCount}` : null;
	}
</script>

<main class="report-container">
	<article class="print-page overview-page">
		<ReportHeader {report} title="AGP-Bericht" pageNumber={1} {pageTotal} />
		<section class="section-block statistics-block">
			<h2>Glukosestatistik und Ziele</h2>
			<GlucoseStatsSection stats={report.glucose_stats} />
		</section>
		<section class="section-block agp-block">
			<h2>Ambulantes Glukoseprofil (AGP)</h2>
			<p class="section-copy">
				Das AGP fasst Glukosewerte aus dem ausgewählten Zeitraum nach Tageszeit zusammen. Median und
				Perzentile werden dargestellt, als beträfen sie einen einzelnen Tag.
			</p>
			<AGPCurve points={report.agp_curve} compact />
		</section>
		<section class="section-block daily-profiles-block">
			<div class="heading-with-note">
				<h2>Tägliche Glukoseprofile</h2>
				{#if report.daily_profiles.length > compactProfiles.length}<span
						>Erste 14 ausgewählte Tage</span
					>{/if}
			</div>
			<p class="section-copy">
				Jedes Profil zeigt Mitternacht bis Mitternacht. Linien werden bei Datenlücken von mehr als
				15 Minuten unterbrochen. Hohl markierte Werte weisen auf mögliche Kompressionswerte hin und
				werden nicht mit der Kurve verbunden.
			</p>
			<DailyProfiles profiles={compactProfiles} compact />
		</section>
	</article>

	<article class="print-page pattern-page">
		<ReportHeader {report} title="Glukosemuster" pageNumber={2} {pageTotal} />
		<section class="section-block pattern-block">
			<h2>Überlagerte Tagesverläufe</h2>
			<p class="section-copy">
				Jede Linie entspricht einem ausgewählten Tag. Die Darstellung zeigt Werte und Zeitbereiche,
				ohne klinische Bewertung oder Handlungsempfehlung.
			</p>
			<GlucosePattern profiles={report.daily_profiles} />
		</section>
	</article>

	{#each monthGroups as month, index}
		<article class="print-page calendar-page">
			<ReportHeader
				{report}
				title="Monatsübersicht"
				pageNote={month.label}
				pageNumber={monthPageStart + index}
				{pageTotal}
			/>
			<section class="section-block calendar-block">
				<h2>{month.label}</h2>
				<p class="section-copy">Dargestellt sind ausschließlich die ausgewählten Berichtstage.</p>
				<MonthlyCalendar days={month.days} />
			</section>
		</article>
	{/each}

	{#each protocolPages as protocols, index}
		<article class="print-page protocol-page">
			<ReportHeader
				{report}
				title="Tagesprotokoll"
				pageNote={protocolNote(index, protocolPages.length)}
				pageNumber={protocolPageStart + index}
				{pageTotal}
			/>
			<section class="section-block protocol-block">
				<h2>Glukoseverlauf und Stundenbereiche</h2>
				<DailyProtocol {protocols} {readingsByDate} />
			</section>
		</article>
	{/each}

	{#each snapshotEventPages as lowEvents, index}
		<article class="print-page snapshot-page" class:snapshot-continuation={index > 0}>
			<ReportHeader
				{report}
				title="Momentaufnahme"
				pageNote={snapshotNote(index, snapshotEventPages.length)}
				pageNumber={snapshotPageStart + index}
				{pageTotal}
			/>
			<section class="section-block snapshot-block">
				{#if index === 0}
					<h2>Zusammenfassung des ausgewählten Zeitraums</h2>
				{/if}
				<ReportSnapshot snapshot={report.snapshot} {lowEvents} showSummary={index === 0} />
			</section>
		</article>
	{/each}

	<article class="print-page meal-page">
		<ReportHeader {report} title="Mahlzeitenprofil" pageNumber={mealPage} {pageTotal} />
		<section class="section-block meal-block">
			<h2>Glukose relativ zu protokollierten Kohlenhydraten</h2>
			<p class="section-copy">
				Die vier Zeitfenster bleiben sichtbar, auch wenn keine Kohlenhydrate protokolliert wurden.
			</p>
			<MealProfile blocks={report.meal_profile} />
		</section>
	</article>

	{#each weeklyPages as days, index}
		<article class="print-page weekly-page">
			<ReportHeader
				{report}
				title="Wochenübersicht"
				pageNote={weeklyNote(index, weeklyPages.length)}
				pageNumber={weeklyPageStart + index}
				{pageTotal}
			/>
			<section class="section-block weekly-block">
				<h2>Tageszeilen</h2>
				<p class="section-copy">
					Jede Seite enthält bis zu sieben ausgewählte Tage. Abdeckung bezeichnet den Anteil
					beobachteter Zeit im jeweiligen Tag.
				</p>
				<WeeklyOverview {days} {readingsByDate} />
			</section>
		</article>
	{/each}

	<article class="print-page daily-pattern-page">
		<ReportHeader {report} title="Tagesmuster" pageNumber={dailyPatternPage} {pageTotal} />
		<section class="section-block daily-pattern-block">
			<h2>Glukose und protokollierte Mengen nach Tageszeit</h2>
			<p class="section-copy">
				Balken zeigen die durchschnittlich pro ausgewähltem Tag protokollierten Kohlenhydrate,
				Schnellinsulin- und Basalinsulinmengen je Zeitintervall.
			</p>
			<DailyPattern points={report.daily_pattern} />
		</section>
	</article>
</main>

<style>
	@page {
		size: A4 portrait;
		margin: 10mm;
	}

	:global(*) {
		-webkit-print-color-adjust: exact;
		print-color-adjust: exact;
	}

	.report-container {
		box-sizing: border-box;
		width: 100%;
		min-width: 0;
		max-width: 210mm;
		margin: 0 auto;
		padding: 0.75rem;
		color: #18313d;
		background: #edf3f4;
	}

	.print-page {
		box-sizing: border-box;
		width: 100%;
		min-width: 0;
		max-width: 100%;
		min-height: 277mm;
		margin: 0 auto 0.8rem;
		padding: 0.9rem;
		background: #fff;
		box-shadow: 0 1px 5px rgb(31 54 63 / 16%);
	}

	.section-block {
		min-width: 0;
		max-width: 100%;
		margin-top: 0.72rem;
		break-inside: avoid;
		page-break-inside: avoid;
	}

	h2 {
		margin: 0 0 0.27rem;
		padding-bottom: 0.22rem;
		border-bottom: 1px solid #a7bec4;
		font-size: 0.95rem;
		line-height: 1.2;
		color: #176b87;
	}

	.section-copy {
		margin: 0 0 0.38rem;
		font-size: 0.69rem;
		line-height: 1.35;
		color: #536b75;
	}

	.heading-with-note {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
		align-items: baseline;
	}

	.heading-with-note span {
		font-size: 0.65rem;
		color: #58707a;
	}

	.overview-page .daily-profiles-block {
		margin-top: 0.56rem;
	}

	.pattern-page .pattern-block {
		margin-top: 1.05rem;
	}

	.calendar-page .calendar-block {
		margin-top: 1.15rem;
	}

	.protocol-page .protocol-block {
		margin-top: 0.55rem;
	}

	.snapshot-page .snapshot-block,
	.meal-page .meal-block,
	.weekly-page .weekly-block,
	.daily-pattern-page .daily-pattern-block {
		margin-top: 1rem;
	}

	@media (max-width: 720px) {
		.report-container {
			padding: 0;
			background: transparent;
		}

		.print-page {
			min-height: 0;
			margin-bottom: 1rem;
			padding: 0.8rem;
			box-shadow: none;
		}
	}

	@media print {
		:global(html),
		:global(body) {
			margin: 0;
			padding: 0;
			background: #fff !important;
		}

		.report-container {
			width: 100%;
			max-width: none;
			margin: 0;
			padding: 0;
			background: #fff;
		}

		.print-page {
			width: auto;
			min-height: 0;
			margin: 0;
			padding: 0;
			box-shadow: none;
			break-after: page;
			page-break-after: always;
			break-inside: avoid;
			page-break-inside: avoid;
		}

		.print-page:last-child {
			break-after: auto;
			page-break-after: auto;
		}

		.section-block {
			margin-top: 3mm;
		}

		h2 {
			margin-bottom: 1mm;
			padding-bottom: 0.8mm;
			font-size: 10pt;
		}

		.section-copy {
			margin-bottom: 1.3mm;
			font-size: 7pt;
		}

		.overview-page .daily-profiles-block,
		.protocol-page .protocol-block {
			margin-top: 2mm;
		}

		.pattern-page .pattern-block,
		.calendar-page .calendar-block,
		.snapshot-page .snapshot-block,
		.meal-page .meal-block,
		.weekly-page .weekly-block,
		.daily-pattern-page .daily-pattern-block {
			margin-top: 4mm;
		}
	}
</style>
