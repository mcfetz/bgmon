import { describe, expect, it } from 'vitest';
import {
	fmtDateTime,
	fmtDuration,
	fmtNullable,
	fmtRatioPct,
	progressPct,
	stageLabel,
	stageUnit,
	verdictLabel,
	verdictReason,
	type MlProgress
} from './mlProgress';

function progress(overrides: Partial<MlProgress> = {}): MlProgress {
	return { stage: 'train', done: 0, total: 3, elapsed_s: null, eta_s: null, ...overrides };
}

describe('progressPct', () => {
	it('uses fixed percentages for the non-counting stages', () => {
		expect(progressPct(progress({ stage: 'starting' }))).toBe(2);
		expect(progressPct(progress({ stage: 'load' }))).toBe(6);
		expect(progressPct(progress({ stage: 'data' }))).toBe(6);
		expect(progressPct(progress({ stage: 'publish' }))).toBe(97);
		expect(progressPct(progress({ stage: 'log' }))).toBe(99);
		expect(progressPct(progress({ stage: 'done' }))).toBe(100);
	});

	it('scales the counting stages across one band of the bar', () => {
		expect(progressPct(progress({ stage: 'train', done: 0, total: 3 }))).toBe(25);
		expect(progressPct(progress({ stage: 'train', done: 1, total: 3 }))).toBe(48);
		expect(progressPct(progress({ stage: 'score', done: 3, total: 3 }))).toBe(95);
	});

	it('never exceeds 100 percent or drops below the band start', () => {
		expect(progressPct(progress({ stage: 'train', done: 99, total: 3 }))).toBe(95);
		expect(progressPct(progress({ stage: 'train', done: -5, total: 3 }))).toBe(25);
	});

	it('keeps the band start when the total is still unknown', () => {
		// The evaluation job only learns its run count once loading finished.
		expect(progressPct(progress({ stage: 'score', done: 0, total: 0 }))).toBe(25);
	});

	it('falls back to zero for an unknown stage', () => {
		expect(progressPct(progress({ stage: 'wat' }))).toBe(0);
	});
});

describe('stageLabel', () => {
	it('labels the stages reported by both jobs', () => {
		expect(stageLabel('load')).toBe('Vorhersagen und Messwerte werden geladen…');
		expect(stageLabel('score')).toBe('Vorhersagen werden bewertet…');
		expect(stageLabel('train')).toBe('Modelle werden trainiert…');
		expect(stageLabel('done')).toBe('Fertig');
	});

	it('falls back for an unknown stage', () => {
		expect(stageLabel('wat')).toBe('Läuft…');
	});
});

describe('stageUnit', () => {
	it('only offers a unit where the counter is meaningful', () => {
		expect(stageUnit('train')).toBe('Horizonte');
		expect(stageUnit('score')).toBe('Vorhersagen');
		expect(stageUnit('load')).toBeNull();
		expect(stageUnit('done')).toBeNull();
	});
});

describe('fmtDuration', () => {
	it('formats seconds, minutes and hours', () => {
		expect(fmtDuration(0)).toBe('0 Sek.');
		expect(fmtDuration(45)).toBe('45 Sek.');
		expect(fmtDuration(60)).toBe('1 Min.');
		expect(fmtDuration(95)).toBe('1 Min. 35 Sek.');
		expect(fmtDuration(3600)).toBe('1 Std. 0 Min.');
		expect(fmtDuration(5430)).toBe('1 Std. 30 Min.');
	});

	it('shows a dash for missing or unusable values', () => {
		expect(fmtDuration(null)).toBe('–');
		expect(fmtDuration(undefined)).toBe('–');
		expect(fmtDuration(Number.NaN)).toBe('–');
		expect(fmtDuration(Number.POSITIVE_INFINITY)).toBe('–');
	});
});
describe('fmtNullable', () => {
	it('formats present metrics and keeps a perfect zero visible', () => {
		expect(fmtNullable(12.34)).toBe('12.3');
		expect(fmtNullable(12.34, 0)).toBe('12');
		// A flawless forecast must not collapse into the "missing" dash.
		expect(fmtNullable(0)).toBe('0.0');
	});

	it('shows a dash when the metric could not be computed', () => {
		expect(fmtNullable(null)).toBe('–');
		expect(fmtNullable(undefined)).toBe('–');
		expect(fmtNullable(Number.NaN)).toBe('–');
		expect(fmtNullable(Number.POSITIVE_INFINITY)).toBe('–');
	});
});

describe('fmtRatioPct', () => {
	it('renders a 0..1 ratio as a percentage', () => {
		expect(fmtRatioPct(0.75)).toBe('75 %');
		expect(fmtRatioPct(1)).toBe('100 %');
		expect(fmtRatioPct(0)).toBe('0 %');
	});

	it('distinguishes no data from zero coverage', () => {
		expect(fmtRatioPct(null)).toBe('–');
		expect(fmtRatioPct(undefined)).toBe('–');
		expect(fmtRatioPct(Number.NaN)).toBe('–');
	});
});

describe('verdictLabel', () => {
	it('maps every verdict onto a readable trust level', () => {
		expect(verdictLabel('conclusive')).toBe('belastbar');
		expect(verdictLabel('provisional')).toBe('vorläufig');
		expect(verdictLabel('insufficient_data')).toBe('nicht aussagekräftig');
		// Unknown values must not read as trustworthy.
		expect(verdictLabel('something_new')).toBe('nicht aussagekräftig');
	});
});

describe('verdictReason', () => {
	it('explains why a number may not be trusted', () => {
		expect(verdictReason('too_few_runs')).toBe('zu wenige Runs');
		expect(verdictReason('too_few_points')).toBe('zu wenige bewertbare Punkte');
		expect(verdictReason('small_sample')).toBe('zu kleine Stichprobe');
		expect(verdictReason('no_baseline')).toBe('keine Baseline verfügbar');
		expect(verdictReason('single_version')).toBe('nur eine Modellversion vorhanden');
	});

	it('stays empty for a conclusive result', () => {
		expect(verdictReason('')).toBe('');
	});
});

describe('fmtDateTime', () => {
	it('renders an ISO timestamp in German short form', () => {
		const formatted = fmtDateTime('2026-10-05T19:31:25+00:00');
		expect(formatted).not.toBe('–');
		// German short form drops the year: day, month, then time.
		expect(formatted).toContain('05.10.');
		expect(formatted).toContain('21:31');
	});

	it('shows a dash for missing or unparsable input', () => {
		expect(fmtDateTime(null)).toBe('–');
		expect(fmtDateTime(undefined)).toBe('–');
		expect(fmtDateTime('')).toBe('–');
		expect(fmtDateTime('not-a-date')).toBe('–');
	});
});
