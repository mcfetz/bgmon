import { describe, expect, it } from 'vitest';
import { fmtDuration, progressPct, stageLabel, stageUnit, type MlProgress } from './mlProgress';

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