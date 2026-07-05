import { apiFetch } from '$lib/auth';

export interface LogEntry {
	id: number;
	entry_type: 'carbs' | 'insulin' | 'basal' | 'note' | 'alarm' | 'success';
	value: number;
	unit: string;
	notes: string | null;
	created_at: string;
	created_by?: string | null;
}

export interface BasalRate {
	rate: number | null;
	unit: string;
	changed_at: string | null;
}

export interface CarbFactor {
	factor: number | null;
	unit: string;
	changed_at: string | null;
}

const BASE = '/api/log';

export async function fetchLogs(): Promise<LogEntry[]> {
	const res = await apiFetch(`${BASE}/`);
	if (!res.ok) return [];
	return res.json();
}

export async function fetchLogsRange(startIso: string, endIso: string): Promise<LogEntry[]> {
	const res = await apiFetch(
		`${BASE}/?start=${encodeURIComponent(startIso)}&end=${encodeURIComponent(endIso)}`
	);
	if (!res.ok) return [];
	return res.json();
}

export async function createLog(
	entry_type: string,
	value: number,
	unit: string,
	notes?: string,
	timestamp?: string
): Promise<{ entry: LogEntry | null; error?: string }> {
	const payload: Record<string, unknown> = { entry_type, value, unit };
	if (notes) payload.notes = notes;
	if (timestamp) payload.timestamp = timestamp;
	const res = await apiFetch(`${BASE}/`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	});
	if (!res.ok) {
		const body = await res.json().catch(() => ({}));
		return { entry: null, error: body.error || `Fehler (${res.status})` };
	}
	return { entry: await res.json() };
}

export async function deleteLog(id: number): Promise<boolean> {
	const res = await apiFetch(`${BASE}/${id}`, {
		method: 'DELETE'
	});
	return res.ok;
}

export async function fetchBasalRate(): Promise<{
	current: BasalRate;
	history: BasalRate[];
} | null> {
	const res = await apiFetch(`${BASE}/basal-rate`);
	if (!res.ok) return null;
	return res.json();
}

export async function updateBasalRate(
	rate: number,
	unit = 'U/h'
): Promise<{ rate: number; unit: string } | null> {
	const res = await apiFetch(`${BASE}/basal-rate`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ rate, unit })
	});
	if (!res.ok) return null;
	return res.json();
}

export async function fetchCarbFactor(): Promise<{
	current: CarbFactor;
	history: CarbFactor[];
} | null> {
	const res = await apiFetch(`${BASE}/carb-factor`);
	if (!res.ok) return null;
	return res.json();
}

export async function updateCarbFactor(
	factor: number,
	unit = 'g/IE'
): Promise<{ factor: number; unit: string } | null> {
	const res = await apiFetch(`${BASE}/carb-factor`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ factor, unit })
	});
	if (!res.ok) return null;
	return res.json();
}

export interface GlobalSettings {
	insulin_action_hours: number;
	correction_factor: number;
}

export async function fetchGlobalSettings(): Promise<GlobalSettings> {
	const res = await apiFetch('/api/settings/global');
	if (!res.ok) return { insulin_action_hours: 4, correction_factor: 50 };
	return res.json();
}
