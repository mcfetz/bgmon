import { apiFetch } from '$lib/auth';

export interface GlucoseReading {
	sgv: number | null;
	trend: number | null;
	direction: string | null;
	timestamp: string | null;
}

export interface LogEntryReading {
	id: number;
	entry_type: 'carbs' | 'insulin' | 'basal' | 'note' | 'alarm' | 'success';
	value: number;
	unit: string;
	notes: string | null;
	created_at: string;
	sync_state?: 'pending' | 'syncing';
	local_id?: string;
}

export interface StatsData {
	mean: number | null;
	tir_percent: number | null;
	tir_below: number | null;
	tir_above: number | null;
	gmi: number | null;
	std_dev: number | null;
	readings: number;
	min: number | null;
	max: number | null;
	streak_hours?: number | null;
	streak_started_at?: string | null;
	best_streak_hours?: number | null;
	best_streak_achieved_at?: string | null;
	daily_score?: {
		total: number;
		level: number;
		progress: number;
		breakdown: { label: string; points: number; count?: number }[];
	} | null;
	weekly_scores?: { date: string; total: number; is_today: boolean }[];
	achievements?: {
		id: string;
		name: string;
		icon: string;
		description: string;
		unlocked: boolean;
	}[];
}

export type TimeRange = 'today' | 'yesterday' | 'this_week' | 'last_week';

const BASE = '/api/dashboard';

export async function fetchCurrent(): Promise<GlucoseReading | null> {
	const res = await apiFetch(`${BASE}/current`);
	if (!res.ok) return null;
	return res.json();
}

export async function fetchHistory(range: TimeRange = 'today'): Promise<GlucoseReading[]> {
	const res = await apiFetch(`${BASE}/history?range=${range}`);
	if (!res.ok) return [];
	return res.json();
}

export async function fetchHistoryRange(start: string, end: string): Promise<GlucoseReading[]> {
	const res = await apiFetch(
		`${BASE}/history?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
	);
	if (!res.ok) return [];
	return res.json();
}

export async function fetchLogsRange(start: string, end: string): Promise<LogEntryReading[]> {
	const res = await apiFetch(
		`${BASE}/logs?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
	);
	if (!res.ok) return [];
	return res.json();
}

export async function fetchStats(range: TimeRange = 'today'): Promise<StatsData | null> {
	const res = await apiFetch(`${BASE}/stats?range=${range}`);
	if (!res.ok) return null;
	return res.json();
}

export async function fetchStatsRange(start: string, end: string): Promise<StatsData | null> {
	const res = await apiFetch(
		`${BASE}/stats?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
	);
	if (!res.ok) return null;
	return res.json();
}

export interface Thresholds {
	critical_low: number;
	low: number;
	high: number;
	critical_high: number;
}

export async function fetchThresholds(): Promise<Thresholds | null> {
	const res = await apiFetch(`${BASE}/thresholds`);
	if (!res.ok) return null;
	return res.json();
}

export interface GlobalSettings {
	insulin_action_hours: number;
}

export async function fetchGlobalSettings(): Promise<GlobalSettings | null> {
	const res = await apiFetch('/api/settings/global');
	if (!res.ok) return null;
	return res.json();
}

export interface PredictionPoint {
	timestamp: string;
	predicted_sgv: number;
	lower_bound: number | null;
	upper_bound: number | null;
}

export type PredictionStatus = 'ready' | 'disabled' | 'unavailable' | 'insufficient_context';

export interface PredictionReady {
	status: 'ready';
	run_id: number;
	generated_at: string;
	context_end_at: string;
	horizon_minutes: number;
	model_version: string;
	model_mae?: number | null;
	baseline_mae?: number | null;
	reused: boolean;
	points: PredictionPoint[];
}

export interface PredictionUnavailable {
	status: 'disabled' | 'unavailable' | 'insufficient_context';
	reason: string;
}

export type PredictionResponse = PredictionReady | PredictionUnavailable;

export async function fetchPrediction(minutes: number = 60): Promise<PredictionResponse | null> {
	const res = await apiFetch(`${BASE}/predictions?minutes=${minutes}`);
	if (!res.ok) return null;
	return res.json();
}
