function formatCalendarDate(year: number, month: number, day: number): string {
	return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

const LOCAL_ISO_TIMESTAMP =
	/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;

export interface LocalTimestampedEvent {
	date: string;
	time: string;
	timestamp: string | null | undefined;
}

/** Parse the API's local wall time and offset without letting the browser convert either. */
export function parseLocalIsoTimestamp(
	value: unknown
): { date: string; time: string; offset: string } | null {
	if (typeof value !== 'string') return null;
	const match = value.match(LOCAL_ISO_TIMESTAMP);
	if (!match) return null;

	return {
		date: match[1],
		time: match[2],
		offset: match[3] === 'Z' ? '+00:00' : match[3]
	};
}

export function formatLowGlucoseEventTime(
	event: LocalTimestampedEvent,
	includeOffset: boolean
): string {
	if (!includeOffset) return event.time;
	const timestamp = parseLocalIsoTimestamp(event.timestamp);
	if (timestamp === null || timestamp.date !== event.date || timestamp.time !== event.time) {
		return event.time;
	}

	return `${event.time} (UTC${timestamp.offset})`;
}

export function formatGermanCalendarDate(value: string): string {
	const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
	return match ? `${match[3]}.${match[2]}.${match[1]}` : value;
}

export function berlinCalendarDate(date: Date): string {
	const parts = new Intl.DateTimeFormat('en-CA', {
		timeZone: 'Europe/Berlin',
		year: 'numeric',
		month: '2-digit',
		day: '2-digit'
	}).formatToParts(date);
	const value = (type: Intl.DateTimeFormatPartTypes) =>
		parts.find((part) => part.type === type)?.value ?? '';
	return `${value('year')}-${value('month')}-${value('day')}`;
}

export function subtractCalendarDays(date: string, days: number): string {
	const [year, month, day] = date.split('-').map(Number);
	const calendarDate = new Date(Date.UTC(year, month - 1, day));
	calendarDate.setUTCDate(calendarDate.getUTCDate() - days);
	return formatCalendarDate(
		calendarDate.getUTCFullYear(),
		calendarDate.getUTCMonth() + 1,
		calendarDate.getUTCDate()
	);
}

export function defaultBerlinReportDates(now: Date): { start: string; end: string } {
	const end = berlinCalendarDate(now);
	return { start: subtractCalendarDays(end, 13), end };
}
