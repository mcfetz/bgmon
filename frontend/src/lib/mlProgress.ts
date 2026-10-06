/**
 * Shared presentation logic for the ML background jobs (training and
 * retrospective evaluation). Both jobs report the same progress shape, so the
 * bar, the stage labels and the duration formatting live here.
 */

export type MlProgress = {
	stage: string;
	done: number;
	total: number;
	elapsed_s: number | null;
	eta_s: number | null;
};

const STAGE_LABELS: Record<string, string> = {
	starting: 'Wird vorbereitet…',
	load: 'Vorhersagen und Messwerte werden geladen…',
	data: 'Trainingsdaten werden gelesen…',
	score: 'Vorhersagen werden bewertet…',
	train: 'Modelle werden trainiert…',
	publish: 'Modell wird veröffentlicht…',
	log: 'Logbucheintrag wird geschrieben…',
	done: 'Fertig'
};

/** Unit of the ``done/total`` counter, for stages that count discrete units. */
const STAGE_UNITS: Record<string, string> = {
	score: 'Vorhersagen',
	train: 'Horizonte'
};

/** Stages whose ``done`` counter is weighted progress rather than real work. */
const FIXED_PCT: Record<string, number> = {
	starting: 2,
	load: 6,
	data: 6,
	publish: 97,
	log: 99,
	done: 100
};

export function stageLabel(stage: string): string {
	return STAGE_LABELS[stage] ?? 'Läuft…';
}

export function stageUnit(stage: string): string | null {
	return STAGE_UNITS[stage] ?? null;
}

export function fmtDuration(seconds: number | null | undefined): string {
	if (seconds == null || !Number.isFinite(seconds)) return '–';
	const s = Math.max(0, Math.round(seconds));
	if (s < 60) return `${s} Sek.`;
	const m = Math.floor(s / 60);
	if (m < 60) return s % 60 ? `${m} Min. ${s % 60} Sek.` : `${m} Min.`;
	return `${Math.floor(m / 60)} Std. ${m % 60} Min.`;
}

export function progressPct(p: MlProgress): number {
	const fixed = FIXED_PCT[p.stage];
	if (fixed !== undefined) return fixed;

	// Weighted part: the per-item loop shares one band of the bar.
	if (p.stage === 'train' || p.stage === 'score') {
		if (p.total <= 0) return 25;
		const ratio = Math.min(Math.max(p.done, 0), p.total) / p.total;
		return Math.round(25 + ratio * 70);
	}
	return 0;
}

/** Render a metric that may legitimately be absent (too few data points). */
export function fmtNullable(value: number | null | undefined, digits = 1): string {
	if (value == null || !Number.isFinite(value)) return '–';
	return value.toFixed(digits);
}

/** Render a 0..1 ratio as a percentage, keeping "no data" distinguishable. */
export function fmtRatioPct(ratio: number | null | undefined): string {
	if (ratio == null || !Number.isFinite(ratio)) return '–';
	return `${Math.round(ratio * 100)} %`;
}

/** German label for how far an evaluation number may be trusted. */
export function verdictLabel(verdict: string): string {
	switch (verdict) {
		case 'conclusive':
			return 'belastbar';
		case 'provisional':
			return 'vorläufig';
		default:
			return 'nicht aussagekräftig';
	}
}

/** Why a verdict came out the way it did. Empty for a conclusive result. */
export function verdictReason(reason: string): string {
	switch (reason) {
		case 'too_few_runs':
			return 'zu wenige Runs';
		case 'too_few_points':
			return 'zu wenige bewertbare Punkte';
		case 'small_sample':
			return 'zu kleine Stichprobe';
		case 'no_baseline':
			return 'keine Baseline verfügbar';
		case 'single_version':
			return 'nur eine Modellversion vorhanden';
		default:
			return '';
	}
}

/**
 * Compact local timestamp for window labels. ``timeZone`` exists so tests can
 * pin the zone instead of depending on the machine they run on.
 */
export function fmtDateTime(iso: string | null | undefined, timeZone?: string): string {
	if (!iso) return '–';
	const parsed = new Date(iso);
	if (Number.isNaN(parsed.getTime())) return '–';
	return parsed.toLocaleString('de-DE', {
		day: '2-digit',
		month: '2-digit',
		hour: '2-digit',
		minute: '2-digit',
		...(timeZone ? { timeZone } : {})
	});
}
