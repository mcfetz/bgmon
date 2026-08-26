import { describe, expect, it } from 'vitest';
import type { GlucosePoint } from '$lib/api/report';
import { glucoseTrace } from './chart';

const xScale = (minutes: number) => minutes;
const yScale = (value: number) => 350 - value;

function point(timestamp: string, sgv: number, isCompressionLow = false): GlucosePoint {
	return {
		timestamp,
		sgv,
		is_compression_low: isCompressionLow,
		trend: null,
		direction: null
	};
}

describe('glucoseTrace', () => {
	it('clips a high raw trace at the plot bound and labels the true cap value', () => {
		const trace = glucoseTrace(
			[point('2026-08-24T08:00:00+02:00', 100), point('2026-08-24T08:05:00+02:00', 500)],
			xScale,
			yScale
		);

		expect(trace.segments).toHaveLength(3);
		expect(trace.caps).toHaveLength(1);
		expect(trace.caps[0].label).toContain('500 mg/dL');
		expect(trace.points).toEqual([]);
	});

	it('keeps target threshold splits within the visible trace', () => {
		const trace = glucoseTrace(
			[point('2026-08-24T08:00:00+02:00', 50), point('2026-08-24T08:05:00+02:00', 260)],
			xScale,
			yScale
		);

		expect(trace.segments.map((segment) => segment.color)).toEqual([
			'#b42318',
			'#e5484d',
			'#4f9d57',
			'#d99a11'
		]);
		expect(trace.segments[0].d).toContain('M484.76190476190476,100L485,90');
	});

	it('breaks a trace at the autumn DST clock rollback', () => {
		const trace = glucoseTrace(
			[point('2026-10-25T02:55:00+02:00', 120), point('2026-10-25T02:00:00+01:00', 125)],
			xScale,
			yScale
		);

		expect(trace.segments).toEqual([]);
	});

	it('breaks at a compression point and exposes a neutral-marker datum', () => {
		const trace = glucoseTrace(
			[
				point('2026-08-24T08:00:00+02:00', 120),
				point('2026-08-24T08:05:00+02:00', 45, true),
				point('2026-08-24T08:10:00+02:00', 120)
			],
			xScale,
			yScale
		);

		expect(trace.segments).toEqual([]);
		expect(trace.compressionPoints).toEqual([
			expect.objectContaining({
				cx: 485,
				cy: 305,
				label: 'Möglicher Kompressionswert: 45 mg/dL'
			})
		]);
		expect(trace.points).toEqual([
			expect.objectContaining({ cx: 480, cy: 230, label: '120 mg/dL' }),
			expect.objectContaining({ cx: 490, cy: 230, label: '120 mg/dL' })
		]);
	});

	it('returns a visible point for exactly one reading', () => {
		const trace = glucoseTrace([point('2026-08-24T08:00:00+02:00', 120)], xScale, yScale);

		expect(trace.points).toEqual([
			expect.objectContaining({ cx: 480, cy: 230, label: '120 mg/dL' })
		]);
	});

	it('renders both endpoints as points when a reading gap exceeds 15 minutes', () => {
		const trace = glucoseTrace(
			[point('2026-08-24T08:00:00+02:00', 120), point('2026-08-24T08:16:00+02:00', 130)],
			xScale,
			yScale
		);

		expect(trace.segments).toEqual([]);
		expect(trace.points).toEqual([
			expect.objectContaining({ cx: 480, cy: 230, label: '120 mg/dL' }),
			expect.objectContaining({ cx: 496, cy: 220, label: '130 mg/dL' })
		]);
	});

	it('batches contiguous fragments with the same color into one SVG path', () => {
		const trace = glucoseTrace(
			[
				point('2026-08-24T08:00:00+02:00', 100),
				point('2026-08-24T08:05:00+02:00', 110),
				point('2026-08-24T08:10:00+02:00', 120)
			],
			xScale,
			yScale
		);

		expect(trace.segments).toEqual([{ d: 'M480,250L485,240L490,230', color: '#4f9d57' }]);
		expect(trace.points).toEqual([]);
	});

	it('does not batch same-color fragments across a reading gap', () => {
		const trace = glucoseTrace(
			[
				point('2026-08-24T08:00:00+02:00', 100),
				point('2026-08-24T08:05:00+02:00', 110),
				point('2026-08-24T08:25:00+02:00', 120),
				point('2026-08-24T08:30:00+02:00', 130)
			],
			xScale,
			yScale
		);

		expect(trace.segments).toEqual([{ d: 'M480,250L485,240M505,230L510,220', color: '#4f9d57' }]);
		expect(trace.points).toEqual([]);
	});

	it('does not reconnect matching positions across a DST fallback break', () => {
		const trace = glucoseTrace(
			[
				point('2026-10-25T01:55:00+02:00', 100),
				point('2026-10-25T02:00:00+02:00', 110),
				point('2026-10-25T02:05:00+02:00', 45, true),
				point('2026-10-25T02:00:00+01:00', 110),
				point('2026-10-25T02:05:00+01:00', 120)
			],
			xScale,
			yScale
		);

		expect(trace.segments).toEqual([{ d: 'M115,250L120,240M120,240L125,230', color: '#4f9d57' }]);
	});
});
