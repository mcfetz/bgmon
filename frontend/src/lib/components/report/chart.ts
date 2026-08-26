import type { GlucosePoint } from '$lib/api/report';

export const GLUCOSE_MIN = 0;
export const GLUCOSE_MAX = 350;
export const GLUCOSE_THRESHOLDS = [54, 70, 180, 250] as const;

export interface SvgSegment {
	d: string;
	color: string;
}

export interface SvgPoint {
	cx: number;
	cy: number;
	color: string;
	label: string;
}

export interface SvgCompressionPoint {
	cx: number;
	cy: number;
	label: string;
}

export interface SvgCapMarker {
	d: string;
	color: string;
	label: string;
}

export interface GlucoseTrace {
	segments: SvgSegment[];
	points: SvgPoint[];
	compressionPoints: SvgCompressionPoint[];
	caps: SvgCapMarker[];
}

interface LocalClock {
	date: string | null;
	minutes: number;
	offsetMinutes: number | null;
}

export function clampGlucose(value: number): number {
	return Math.max(GLUCOSE_MIN, Math.min(GLUCOSE_MAX, value));
}

export function timeOfDayMinutes(timestamp: string): number {
	return localClock(timestamp).minutes;
}

export function glucoseBandColor(value: number): string {
	if (value < 54) return '#b42318';
	if (value < 70) return '#e5484d';
	if (value <= 180) return '#4f9d57';
	if (value <= 250) return '#d99a11';
	return '#b42318';
}

function pointTimestamp(point: GlucosePoint): number {
	const timestamp = Date.parse(point.timestamp);
	return Number.isNaN(timestamp) ? Number.NaN : timestamp;
}

function interpolate(start: number, end: number, fraction: number): number {
	if (fraction === 0) return start;
	if (fraction === 1) return end;
	return start + (end - start) * fraction;
}

function localClock(timestamp: string): LocalClock {
	// Backend timestamps contain the display-local ISO clock time. Keep that clock time
	// rather than converting it to the browser's timezone.
	const clockMatch = timestamp.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/);
	if (!clockMatch) return { date: null, minutes: 0, offsetMinutes: null };

	const offsetMatch = timestamp.match(/(Z|[+-]\d{2}:?\d{2})$/);
	let offsetMinutes: number | null = null;
	if (offsetMatch?.[1] === 'Z') {
		offsetMinutes = 0;
	} else if (offsetMatch?.[1]) {
		const [, sign, hours, minutes] = offsetMatch[1].match(/^([+-])(\d{2}):?(\d{2})$/) ?? [];
		if (sign && hours && minutes) {
			const magnitude = Number(hours) * 60 + Number(minutes);
			offsetMinutes = sign === '+' ? magnitude : -magnitude;
		}
	}

	return {
		date: clockMatch[1],
		minutes: Number(clockMatch[2]) * 60 + Number(clockMatch[3]),
		offsetMinutes
	};
}

function hasValidPosition(point: GlucosePoint): boolean {
	return (
		Number.isFinite(point.sgv) &&
		Number.isFinite(pointTimestamp(point)) &&
		localClock(point.timestamp).date !== null
	);
}

function isValidTracePoint(point: GlucosePoint): boolean {
	return !point.is_compression_low && hasValidPosition(point);
}

function capMarker(
	value: number,
	x: number,
	yScale: (value: number) => number
): SvgCapMarker | null {
	if (value >= GLUCOSE_MIN && value <= GLUCOSE_MAX) return null;

	const above = value > GLUCOSE_MAX;
	const y = yScale(above ? GLUCOSE_MAX : GLUCOSE_MIN);
	const size = 3.5;
	const d = above
		? `M${x},${y + 0.5}L${x - size},${y + size * 1.7}L${x + size},${y + size * 1.7}Z`
		: `M${x},${y - 0.5}L${x - size},${y - size * 1.7}L${x + size},${y - size * 1.7}Z`;

	return {
		d,
		color: glucoseBandColor(value),
		label: `${value} mg/dL außerhalb des dargestellten Bereichs 0-350 mg/dL`
	};
}

/** Return at most one upper and one lower cap marker for each x position. */
export function glucoseRangeCapMarkers(
	valueGroups: readonly (readonly (number | null)[])[],
	xScale: (index: number) => number,
	yScale: (value: number) => number
): SvgCapMarker[] {
	const markers: SvgCapMarker[] = [];
	const count = Math.max(0, ...valueGroups.map((values) => values.length));

	for (let index = 0; index < count; index += 1) {
		const values = valueGroups
			.map((group) => group[index])
			.filter((value): value is number => typeof value === 'number');
		if (values.length === 0) continue;

		const lowest = Math.min(...values);
		const highest = Math.max(...values);
		const x = xScale(index);
		const lowerCap = lowest < GLUCOSE_MIN ? capMarker(lowest, x, yScale) : null;
		const upperCap = highest > GLUCOSE_MAX ? capMarker(highest, x, yScale) : null;
		if (lowerCap) markers.push(lowerCap);
		if (upperCap) markers.push(upperCap);
	}

	return markers;
}

function canConnect(start: GlucosePoint, end: GlucosePoint, maxGapMinutes: number): boolean {
	if (!isValidTracePoint(start) || !isValidTracePoint(end)) return false;

	const startTimestamp = pointTimestamp(start);
	const endTimestamp = pointTimestamp(end);
	const gapMilliseconds = endTimestamp - startTimestamp;
	if (
		!Number.isFinite(gapMilliseconds) ||
		gapMilliseconds <= 0 ||
		gapMilliseconds > maxGapMinutes * 60 * 1000
	) {
		return false;
	}

	const startClock = localClock(start.timestamp);
	const endClock = localClock(end.timestamp);
	if (
		startClock.date === null ||
		endClock.date === null ||
		startClock.date !== endClock.date ||
		endClock.minutes < startClock.minutes
	) {
		return false;
	}

	// Break both DST transitions. A line would otherwise bridge a skipped local
	// hour in spring or move backwards through the repeated hour in autumn.
	return (
		startClock.offsetMinutes === null ||
		endClock.offsetMinutes === null ||
		startClock.offsetMinutes === endClock.offsetMinutes
	);
}

function crossingFraction(start: number, end: number, value: number): number | null {
	const delta = end - start;
	if (delta === 0) return null;
	const fraction = (value - start) / delta;
	return fraction > 0 && fraction < 1 ? fraction : null;
}

/**
 * Build a trace from raw points without letting values outside the chart domain
 * masquerade as exactly 0 or 350 mg/dL. Visible line fragments are clipped at
 * the bounds and every out-of-range observation receives an arrow marker.
 */
export function glucoseTrace(
	observations: readonly GlucosePoint[],
	xScale: (minutes: number) => number,
	yScale: (value: number) => number,
	maxGapMinutes = 15
): GlucoseTrace {
	const segments: SvgSegment[] = [];
	const connectedPointIndexes = new Set<number>();
	const segmentsByColor = new Map<
		string,
		{ segment: SvgSegment; endX: number; endY: number; runId: number }
	>();
	let runId = 0;
	const caps = observations.flatMap((point) => {
		if (!isValidTracePoint(point)) return [];
		const marker = capMarker(point.sgv, xScale(timeOfDayMinutes(point.timestamp)), yScale);
		return marker ? [marker] : [];
	});
	const compressionPoints = observations
		.filter((point) => point.is_compression_low && hasValidPosition(point))
		.map((point) => ({
			cx: xScale(timeOfDayMinutes(point.timestamp)),
			cy: yScale(clampGlucose(point.sgv)),
			label: `Möglicher Kompressionswert: ${point.sgv} mg/dL`
		}));

	for (let index = 0; index < observations.length - 1; index += 1) {
		const start = observations[index];
		const end = observations[index + 1];
		if (!canConnect(start, end, maxGapMinutes)) {
			runId += 1;
			continue;
		}

		const fractions = [0, 1];
		for (const threshold of [...GLUCOSE_THRESHOLDS, GLUCOSE_MIN, GLUCOSE_MAX]) {
			const fraction = crossingFraction(start.sgv, end.sgv, threshold);
			if (fraction !== null) fractions.push(fraction);
		}
		fractions.sort((first, second) => first - second);
		const splitFractions = fractions.filter(
			(fraction, fractionIndex) =>
				fractionIndex === 0 || Math.abs(fraction - fractions[fractionIndex - 1]) > Number.EPSILON
		);

		const startMinutes = timeOfDayMinutes(start.timestamp);
		const endMinutes = timeOfDayMinutes(end.timestamp);
		let hasVisibleFragment = false;
		for (let fractionIndex = 0; fractionIndex < splitFractions.length - 1; fractionIndex += 1) {
			const from = splitFractions[fractionIndex];
			const to = splitFractions[fractionIndex + 1];
			const midpoint = (from + to) / 2;
			const fromValue = interpolate(start.sgv, end.sgv, from);
			const toValue = interpolate(start.sgv, end.sgv, to);
			const midpointValue = interpolate(start.sgv, end.sgv, midpoint);
			if (midpointValue < GLUCOSE_MIN || midpointValue > GLUCOSE_MAX) continue;
			const fromMinutes = interpolate(startMinutes, endMinutes, from);
			const toMinutes = interpolate(startMinutes, endMinutes, to);
			const fromX = xScale(fromMinutes);
			const fromY = yScale(clampGlucose(fromValue));
			const toX = xScale(toMinutes);
			const toY = yScale(clampGlucose(toValue));
			const color = glucoseBandColor(midpointValue);

			const existing = segmentsByColor.get(color);
			if (existing) {
				// Use a new move command across gaps or another glucose band. One
				// SVG path per color keeps long multi-day report charts inexpensive.
				existing.segment.d +=
					existing.runId === runId && existing.endX === fromX && existing.endY === fromY
						? `L${toX},${toY}`
						: `M${fromX},${fromY}L${toX},${toY}`;
				existing.endX = toX;
				existing.endY = toY;
				existing.runId = runId;
			} else {
				const segment: SvgSegment = { d: `M${fromX},${fromY}L${toX},${toY}`, color };
				segments.push(segment);
				segmentsByColor.set(color, { segment, endX: toX, endY: toY, runId });
			}

			hasVisibleFragment = true;
			if (from === 0) connectedPointIndexes.add(index);
			if (to === 1) connectedPointIndexes.add(index + 1);
		}

		if (!hasVisibleFragment) continue;
	}

	return {
		segments,
		caps,
		compressionPoints,
		points: observations.flatMap((point, index) => {
			if (
				!isValidTracePoint(point) ||
				connectedPointIndexes.has(index) ||
				point.sgv < GLUCOSE_MIN ||
				point.sgv > GLUCOSE_MAX
			) {
				return [];
			}
			return [
				{
					cx: xScale(timeOfDayMinutes(point.timestamp)),
					cy: yScale(clampGlucose(point.sgv)),
					color: glucoseBandColor(point.sgv),
					label: `${point.sgv} mg/dL`
				}
			];
		})
	};
}

/** Kept for simple path-only consumers; raw report charts use glucoseTrace. */
export function glucoseSegmentPaths(
	points: readonly GlucosePoint[],
	xScale: (minutes: number) => number,
	yScale: (value: number) => number,
	maxGapMinutes = 15
): SvgSegment[] {
	return glucoseTrace(points, xScale, yScale, maxGapMinutes).segments;
}

export function linePath(
	values: readonly (number | null)[],
	xScale: (index: number) => number,
	yScale: (value: number) => number
): string {
	let path = '';
	let isConnected = false;

	for (let index = 0; index < values.length; index += 1) {
		const value = values[index];
		if (value === null) {
			isConnected = false;
			continue;
		}
		const command = isConnected ? 'L' : 'M';
		path += `${command}${xScale(index)},${yScale(value)}`;
		isConnected = true;
	}

	return path;
}

export function areaPaths(
	lower: readonly (number | null)[],
	upper: readonly (number | null)[],
	xScale: (index: number) => number,
	yScale: (value: number) => number
): string[] {
	const paths: string[] = [];
	let run: number[] = [];

	function finishRun() {
		if (run.length >= 2) {
			const lowerPath = run.map((index) => `${xScale(index)},${yScale(lower[index]!)}`);
			const upperPath = [...run]
				.reverse()
				.map((index) => `${xScale(index)},${yScale(upper[index]!)}`);
			paths.push(`M${lowerPath.join('L')}L${upperPath.join('L')}Z`);
		}
		run = [];
	}

	for (let index = 0; index < Math.min(lower.length, upper.length); index += 1) {
		if (lower[index] === null || upper[index] === null) {
			finishRun();
			continue;
		}
		run.push(index);
	}
	finishRun();

	return paths;
}

export function formatNumber(value: number | null, maximumFractionDigits = 1): string {
	if (value === null) return '–';
	return value.toLocaleString('de-DE', { maximumFractionDigits });
}
