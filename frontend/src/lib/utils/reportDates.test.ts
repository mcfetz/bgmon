import { describe, expect, it } from 'vitest';
import {
	defaultBerlinReportDates,
	formatGermanCalendarDate,
	formatLowGlucoseEventTime,
	subtractCalendarDays
} from './reportDates';

describe('Berlin report dates', () => {
	it('uses Berlin calendar days for a 14-day range across the spring DST change', () => {
		expect(defaultBerlinReportDates(new Date('2026-03-29T12:00:00.000Z'))).toEqual({
			start: '2026-03-16',
			end: '2026-03-29'
		});
	});

	it('subtracts calendar dates without a fixed millisecond day', () => {
		expect(subtractCalendarDays('2026-10-25', 13)).toBe('2026-10-12');
	});

	it('formats ISO calendar dates without converting their timezone', () => {
		expect(formatGermanCalendarDate('2026-08-24')).toBe('24.08.2026');
		expect(formatGermanCalendarDate('2026-08-24T00:00:00.000Z')).toBe('24.08.2026');
	});

	it('keeps DST fallback low-event wall times and distinguishes their offsets', () => {
		expect(
			formatLowGlucoseEventTime(
				{
					date: '2026-10-25',
					time: '02:05',
					timestamp: '2026-10-25T02:05:00+02:00'
				},
				true
			)
		).toBe('02:05 (UTC+02:00)');
		expect(
			formatLowGlucoseEventTime(
				{
					date: '2026-10-25',
					time: '02:05',
					timestamp: '2026-10-25T02:05:00+01:00'
				},
				true
			)
		).toBe('02:05 (UTC+01:00)');
		expect(
			formatLowGlucoseEventTime(
				{
					date: '2026-10-25',
					time: '02:05',
					timestamp: '2026-10-25T02:05:00+01:00'
				},
				false
			)
		).toBe('02:05');
	});
});
