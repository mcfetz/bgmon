import { apiFetch } from '$lib/auth';

export interface ReportPeriod {
	start: string;
	end: string;
	num_days: number;
}

export interface GlucoseStats {
	mean: number | null;
	tir_percent: number | null;
	tir_below: number | null;
	tir_above: number | null;
	gmi: number | null;
	gmi_mmol_mol: number | null;
	cv_percent: number | null;
	std_dev: number | null;
	readings: number;
	min_val: number | null;
	max_val: number | null;
	data_coverage_percent: number;
	time_below_54_percent: number | null;
	time_54_70_percent: number | null;
	time_70_180_percent: number | null;
	time_180_250_percent: number | null;
	time_above_250_percent: number | null;
}

export interface AGPPoint {
	bucket_index: number;
	time_label: string;
	p5: number | null;
	p25: number | null;
	p50: number | null;
	p75: number | null;
	p95: number | null;
}

export interface GlucosePoint {
	timestamp: string;
	sgv: number;
	is_compression_low: boolean;
	trend: number | null;
	direction: string | null;
}

export interface DailyProfile {
	date: string;
	weekday: string;
	readings: GlucosePoint[];
	avg: number | null;
	/** Logged carbohydrates normalized to grams (KE entries are multiplied by 10). */
	carbs_total: number;
	rapid_insulin_total: number;
	basal_insulin_total: number;
	total_insulin: number;
	low_events: number;
	data_coverage_percent: number;
}

export interface DayOverview {
	date: string;
	weekday: string;
	avg_sgv: number | null;
	/** Logged carbohydrates normalized to grams (KE entries are multiplied by 10). */
	carbs_total: number;
	rapid_insulin_total: number;
	basal_insulin_total: number;
	total_insulin: number;
	low_events: number;
	reading_count: number;
	data_coverage_percent: number;
}

export interface IntervalMinMax {
	hour: number;
	time_start: string;
	time_end: string;
	min_val: number | null;
	max_val: number | null;
}

export interface LogMarker {
	timestamp: string;
	kind: 'carbs' | 'rapid_insulin' | 'basal' | 'note';
	value: number;
	unit: string;
	notes: string | null;
}

export interface DayProtocol {
	date: string;
	weekday: string;
	intervals: IntervalMinMax[];
	markers: LogMarker[];
	marker_count: number;
	markers_truncated: boolean;
}

export interface LowGlucoseEvent {
	date: string;
	time: string;
	timestamp: string;
	sgv: number;
	duration_minutes: number;
}

export interface CoveragePoint {
	time_start: string;
	time_end: string;
	data_coverage_percent: number;
}

export interface ReportSnapshot {
	mean_sgv: number | null;
	gmi: number | null;
	gmi_mmol_mol: number | null;
	tir_percent: number | null;
	below_percent: number | null;
	above_percent: number | null;
	low_events_count: number;
	low_events_avg_duration_minutes: number | null;
	data_coverage_percent: number;
	carbs_daily_avg: number;
	rapid_insulin_daily_avg: number;
	basal_insulin_daily_avg: number;
	total_insulin_daily_avg: number;
	coverage_profile: CoveragePoint[];
	low_events: LowGlucoseEvent[];
	low_events_truncated: boolean;
}

export interface MealPoint {
	offset_label: string;
	median_sgv: number | null;
	p25: number | null;
	p75: number | null;
}

export interface MealBlock {
	name: string;
	hours_label: string;
	points: MealPoint[];
}

export interface DailyPatternPoint {
	time_label: string;
	p5: number | null;
	p25: number | null;
	p50: number | null;
	p75: number | null;
	p95: number | null;
	carbs_avg: number;
	rapid_insulin_avg: number;
	basal_insulin_avg: number;
}

export interface WeeklyDay {
	date: string;
	weekday: string;
	avg_sgv: number | null;
	/** Logged carbohydrates normalized to grams (KE entries are multiplied by 10). */
	carbs_total: number;
	rapid_insulin_total: number;
	basal_insulin_total: number;
	total_insulin: number;
	low_events: number;
	reading_count: number;
	data_coverage_percent: number;
}

export interface ReportData {
	patient_name: string;
	generated_at: string;
	timezone: string;
	period: ReportPeriod;
	glucose_stats: GlucoseStats;
	agp_curve: AGPPoint[];
	daily_profiles: DailyProfile[];
	monthly_overview: DayOverview[];
	daily_protocols: DayProtocol[];
	snapshot: ReportSnapshot;
	meal_profile: MealBlock[];
	daily_pattern: DailyPatternPoint[];
	weekly_overview: WeeklyDay[];
}

const REPORT_ERROR_MESSAGES: Record<string, string> = {
	no_patient: 'Für den Bericht ist kein Patient eingerichtet.',
	multiple_patients:
		'Der Bericht kann nur mit genau einem eingerichteten Patienten erstellt werden.',
	'account deactivated': 'Dieses Konto wurde deaktiviert.',
	account_deactivated: 'Dieses Konto wurde deaktiviert.',
	future_date_not_allowed: 'Der Berichtszeitraum darf keine zukünftigen Tage enthalten.',
	invalid_date_format: 'Bitte geben Sie die Daten im Format JJJJ-MM-TT an.',
	invalid_format: 'Bitte geben Sie die Daten im Format JJJJ-MM-TT an.',
	max_days: 'Der Berichtszeitraum darf höchstens 90 Tage umfassen.',
	max_days_exceeded: 'Der Berichtszeitraum darf höchstens 90 Tage umfassen.',
	report_data_limit_exceeded:
		'Für diesen Berichtszeitraum liegen zu viele Daten vor. Bitte wählen Sie einen kürzeren Zeitraum.',
	rate_limit_exceeded:
		'Zu viele Berichte wurden angefordert. Bitte versuchen Sie es gleich noch einmal.',
	invalid_date_range: 'Der gewählte Berichtszeitraum wird nicht unterstützt.',
	start_before_end: 'Das Startdatum muss am oder vor dem Enddatum liegen.',
	start_after_end: 'Das Startdatum muss am oder vor dem Enddatum liegen.'
};

function localizedReportMessage(value: unknown): string | null {
	if (typeof value !== 'string') return null;
	const message = value.trim();
	if (!message) return null;

	return /[äöüß]|\b(?:bericht|datum|tage|startdatum|enddatum|ungültig|zukünftig|kein|keine|höchstens)\b/iu.test(
		message
	)
		? message
		: null;
}

export function reportErrorMessage(payload: unknown, status: number): string {
	const error =
		payload !== null && typeof payload === 'object' && 'error' in payload
			? (payload as { error?: unknown }).error
			: undefined;
	const message =
		payload !== null && typeof payload === 'object' && 'message' in payload
			? (payload as { message?: unknown }).message
			: undefined;
	const code = typeof error === 'string' ? error.trim().toLowerCase() : '';

	if (REPORT_ERROR_MESSAGES[code]) return REPORT_ERROR_MESSAGES[code];
	if (/ungültig.*datumsformat|invalid.*date.*format/iu.test(code)) {
		return REPORT_ERROR_MESSAGES.invalid_date_format;
	}
	if (/maximal.*tage|max.*days/iu.test(code)) return REPORT_ERROR_MESSAGES.max_days;
	if (/startdatum.*enddatum|start.*(?:before|after).*end/iu.test(code)) {
		return REPORT_ERROR_MESSAGES.start_before_end;
	}

	return (
		localizedReportMessage(message) ?? `Bericht konnte nicht erstellt werden (HTTP ${status}).`
	);
}

export async function fetchReport(start: string, end: string): Promise<ReportData> {
	const resp = await apiFetch(`/api/report?start=${start}&end=${end}`);
	if (!resp.ok) {
		const err: unknown = await resp.json().catch(() => null);
		throw new Error(reportErrorMessage(err, resp.status));
	}
	return resp.json();
}
