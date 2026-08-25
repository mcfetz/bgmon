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
	cv_percent: number | null;
	std_dev: number | null;
	readings: number;
	min_val: number | null;
	max_val: number | null;
	sensor_active_percent: number | null;
	time_below_54: number | null;
	time_54_70: number | null;
	time_70_180: number | null;
	time_180_250: number | null;
	time_above_250: number | null;
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

export interface DailyProfile {
	date: string;
	weekday: string;
	readings: [string, number][];
	avg: number | null;
	carbs_total: number | null;
	insulin_total: number | null;
	hypo_events: number;
}

export interface DayOverview {
	date: string;
	weekday: string;
	avg_sgv: number | null;
	carbs_grams: number | null;
	insulin_units: number | null;
	hypo_events: number;
	reading_count: number;
}

export interface IntervalMinMax {
	time_start: string;
	time_end: string;
	min_val: number | null;
	max_val: number | null;
}

export interface DayProtocol {
	date: string;
	weekday: string;
	intervals: IntervalMinMax[];
}

export interface LowGlucoseEvent {
	date: string;
	time: string;
	sgv: number;
	duration_minutes: number;
}

export interface ReportSnapshot {
	mean_sgv: number | null;
	gmi: number | null;
	tir_percent: number | null;
	below_percent: number | null;
	above_percent: number | null;
	low_events_count: number;
	low_events_avg_duration_minutes: number | null;
	sensor_active_percent: number | null;
	avg_scans_per_day: number | null;
	carbs_daily_avg_grams: number | null;
	insulin_daily_avg_units: number | null;
	low_events: LowGlucoseEvent[];
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
	carbs_avg: number | null;
	insulin_avg: number | null;
}

export interface WeeklyDay {
	date: string;
	weekday: string;
	glucose_points: [string, number][];
	avg_sgv: number | null;
	carbs_grams: number | null;
	insulin_units: number | null;
	hypo_events: number;
}

export interface ReportData {
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

export async function fetchReport(start: string, end: string): Promise<ReportData> {
	const resp = await apiFetch(`/api/report?start=${start}&end=${end}`);
	if (!resp.ok) {
		const err = await resp.json().catch(() => ({ error: 'Unbekannter Fehler' }));
		throw new Error(err.error || `HTTP ${resp.status}`);
	}
	return resp.json();
}
