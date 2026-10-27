<script lang="ts">
	import type { DayProtocol, GlucosePoint, LogMarker, SettingChange } from '#lib/api/report.js';
	import {
		clampGlucose,
		formatNumber,
		glucoseTrace,
		timeOfDayMinutes,
		type GlucoseTrace
	} from './chart';

	let {
		protocols,
		readingsByDate
	}: {
		protocols: DayProtocol[];
		readingsByDate: ReadonlyMap<string, GlucosePoint[]>;
	} = $props();

	const width = 850;
	const height = 112;
	const pad = { top: 14, right: 14, bottom: 28, left: 30 };
	const chartWidth = width - pad.left - pad.right;
	const chartHeight = height - pad.top - pad.bottom;

	function xScale(minutes: number): number {
		return pad.left + (minutes / 1440) * chartWidth;
	}

	function yScale(value: number): number {
		return pad.top + chartHeight - (clampGlucose(value) / 350) * chartHeight;
	}

	function trace(readings: GlucosePoint[]): GlucoseTrace {
		return glucoseTrace(readings, xScale, yScale);
	}

	function shortDate(date: string): string {
		const months = [
			'JAN',
			'FEB',
			'MAR',
			'APR',
			'MAI',
			'JUN',
			'JUL',
			'AUG',
			'SEP',
			'OKT',
			'NOV',
			'DEZ'
		];
		return `${date.slice(8)}. ${months[Number(date.slice(5, 7)) - 1]}`;
	}

	function markerColor(marker: LogMarker): string {
		if (marker.kind === 'carbs') return '#b57600';
		if (marker.kind === 'rapid_insulin') return '#176b87';
		if (marker.kind === 'correction') return '#b3261e';
		return '#5c4b8a';
	}

	function markerTitle(marker: LogMarker): string {
		const kind =
			marker.kind === 'carbs'
				? 'Kohlenhydrate'
				: marker.kind === 'rapid_insulin'
					? 'Schnellinsulin'
					: marker.kind === 'correction'
						? 'Korrekturinsulin (ohne KH im 15-Minuten-Fenster)'
						: 'Basalinsulin';
		const value = `${marker.value}${marker.unit}`;
		return [marker.timestamp, kind, value, marker.notes?.trim()].filter(Boolean).join(' · ');
	}

	function markerLabel(marker: LogMarker): string {
		return `${marker.value}${marker.unit}`;
	}

	function markerSymbol(marker: LogMarker): string {
		if (marker.kind === 'carbs') return 'KH';
		if (marker.kind === 'rapid_insulin') return 'S';
		if (marker.kind === 'correction') return 'K';
		return 'B';
	}

	interface PlacedMarker {
		marker: LogMarker;
		x: number;
		y: number;
		label: string;
		labelX: number;
		anchor: 'start' | 'end';
	}

	const MARKER_LANE_Y = [0, 1, 2, 3].map((lane) => pad.top + 4 + lane * 8.6);
	const MARKER_LABEL_OFFSET = 7;
	const MARKER_LABEL_CHAR_WIDTH = 4.2;

	function layoutMarkers(markers: LogMarker[]): PlacedMarker[] {
		const laneEnds = MARKER_LANE_Y.map(() => Number.NEGATIVE_INFINITY);
		return markers.map((marker) => {
			const x = xScale(timeOfDayMinutes(marker.timestamp));
			const label = markerLabel(marker);
			const labelWidth = MARKER_LABEL_OFFSET + label.length * MARKER_LABEL_CHAR_WIDTH;
			let lane = laneEnds.findIndex((end) => x - MARKER_LABEL_OFFSET >= end);
			if (lane === -1) {
				lane = laneEnds.indexOf(Math.min(...laneEnds));
			}
			laneEnds[lane] = x + labelWidth;
			const anchor = x > width - pad.right - labelWidth ? 'end' : 'start';
			return {
				marker,
				x,
				y: MARKER_LANE_Y[lane],
				label,
				labelX: anchor === 'end' ? -MARKER_LABEL_OFFSET : MARKER_LABEL_OFFSET,
				anchor
			};
		});
	}

	interface PlacedSettingChange {
		change: SettingChange;
		x: number;
		y: number;
		label: string;
		anchor: 'start' | 'middle' | 'end';
	}

	const SETTING_LABEL_Y = [90, 97];
	const SETTING_LABEL_CHAR_WIDTH = 3.2;
	const SETTING_LABEL_GAP = 4;

	function settingChangeColor(change: SettingChange): string {
		return change.kind === 'carb_factor' ? '#b57600' : '#5c4b8a';
	}

	function settingChangeLabel(change: SettingChange): string {
		const current = formatNumber(change.value);
		const previous = change.previous === null ? null : formatNumber(change.previous);
		if (change.kind === 'carb_factor') {
			return previous === null ? `KE-Faktor ${current}` : `KE-Faktor ${previous} → ${current}`;
		}
		const unit = ` ${change.unit}`;
		return previous === null ? `Basal ${current}${unit}` : `Basal ${previous} → ${current}${unit}`;
	}

	function layoutSettingChanges(changes: SettingChange[]): PlacedSettingChange[] {
		const rowEnds = SETTING_LABEL_Y.map(() => Number.NEGATIVE_INFINITY);
		return changes.map((change) => {
			const x = xScale(timeOfDayMinutes(change.timestamp));
			const label = settingChangeLabel(change);
			const halfWidth = (label.length * SETTING_LABEL_CHAR_WIDTH) / 2;
			let row = rowEnds.findIndex((end) => x - halfWidth - SETTING_LABEL_GAP >= end);
			if (row === -1) {
				row = rowEnds.indexOf(Math.min(...rowEnds));
			}
			rowEnds[row] = x + halfWidth;
			const anchor: PlacedSettingChange['anchor'] =
				x < pad.left + halfWidth ? 'start' : x > width - pad.right - halfWidth ? 'end' : 'middle';
			return { change, x, y: SETTING_LABEL_Y[row], label, anchor };
		});
	}

	function valueClass(value: number | null): string {
		if (value === null) return 'empty';
		if (value < 70 || value > 250) return 'outlier';
		if (value > 180) return 'high';
		return '';
	}
</script>

<div class="protocols">
	{#each protocols as protocol}
		{@const readings = readingsByDate.get(protocol.date) ?? []}
		{@const chart = trace(readings)}
		{@const markerLayout = layoutMarkers(protocol.markers)}
		{@const settingChanges = layoutSettingChanges(protocol.setting_changes)}
		<article class="protocol-panel">
			<header class="protocol-header">
				<strong>{protocol.weekday.toUpperCase()} {shortDate(protocol.date)}</strong>
				<span
					>{readings.length
						? `${readings.length} dargestellte Glukosewerte`
						: 'Keine Glukosedaten'}</span
				>
			</header>
			<div class="trace-scroll">
				<svg
					viewBox={`0 0 ${width} ${height}`}
					class="trace"
					role="img"
					aria-label={`Glukoseverlauf ${protocol.date}`}
				>
					<rect
						x={pad.left}
						y={yScale(180)}
						width={chartWidth}
						height={yScale(70) - yScale(180)}
						fill="#dcefdc"
					/>
					{#each [0, 70, 180, 350] as value}
						<line
							x1={pad.left}
							y1={yScale(value)}
							x2={pad.left + chartWidth}
							y2={yScale(value)}
							class:threshold={value === 70 || value === 180}
							class="grid"
						/>
						<text x={pad.left - 5} y={yScale(value) + 3} text-anchor="end" class="axis"
							>{value}</text
						>
					{/each}
					{#each Array.from({ length: 13 }, (_, index) => index * 2) as hour}
						<line
							x1={xScale(hour * 60)}
							y1={pad.top}
							x2={xScale(hour * 60)}
							y2={pad.top + chartHeight}
							class="vertical"
						/>
						<text x={xScale(hour * 60)} y={height - 4} text-anchor="middle" class="axis"
							>{String(hour).padStart(2, '0')}</text
						>
					{/each}
					<text x={pad.left} y={10} class="unit">mg/dL</text>
					{#each settingChanges as placed}
						<line
							x1={placed.x}
							y1={pad.top}
							x2={placed.x}
							y2={pad.top + chartHeight}
							class="setting-line"
							stroke={settingChangeColor(placed.change)}
						/>
					{/each}
					{#each chart.segments as segment}
						<path
							d={segment.d}
							fill="none"
							stroke={segment.color}
							stroke-width="1.65"
							stroke-linecap="round"
						/>
					{/each}
					{#each chart.points as point}
						<circle
							cx={point.cx}
							cy={point.cy}
							r="2.7"
							fill={point.color}
							stroke="#fff"
							stroke-width="0.9"
						>
							<title>{point.label}</title>
						</circle>
					{/each}
					{#each chart.compressionPoints as point}
						<circle cx={point.cx} cy={point.cy} r="3" class="compression-point">
							<title>{point.label}</title>
						</circle>
					{/each}
					{#each chart.caps as cap}
						<path d={cap.d} fill={cap.color} stroke="#fff" stroke-width="0.7">
							<title>{cap.label}</title>
						</path>
					{/each}
					{#each markerLayout as placed}
						<g transform={`translate(${placed.x} ${placed.y})`}>
							<title>{markerTitle(placed.marker)}</title>
							<circle r="3.9" fill={markerColor(placed.marker)} stroke="#fff" stroke-width="0.9" />
							<text y="1.5" text-anchor="middle" class="marker-symbol"
								>{markerSymbol(placed.marker)}</text
							>
							<text
								x={placed.labelX}
								y="2.2"
								text-anchor={placed.anchor}
								class="marker-value"
								fill={markerColor(placed.marker)}>{placed.label}</text
							>
						</g>
					{/each}
					{#each settingChanges as placed}
						<text
							x={placed.x}
							y={placed.y}
							text-anchor={placed.anchor}
							class="setting-label"
							fill={settingChangeColor(placed.change)}>{placed.label}</text
						>
					{/each}
				</svg>
			</div>
			<div class="ranges-scroll">
				<div class="ranges" aria-label={`Stundenbereiche ${protocol.date}`}>
					<div class="range-row labels">
						<span></span>{#each protocol.intervals as interval}<span
								>{String(interval.hour).padStart(2, '0')}</span
							>{/each}
					</div>
					<div class="range-row">
						<b>Max.</b>{#each protocol.intervals as interval}<span
								class={valueClass(interval.max_val)}>{interval.max_val ?? '-'}</span
							>{/each}
					</div>
					<div class="range-row">
						<b>Min.</b>{#each protocol.intervals as interval}<span
								class={valueClass(interval.min_val)}>{interval.min_val ?? '-'}</span
							>{/each}
					</div>
				</div>
			</div>
			{#if protocol.markers_truncated}
				<p class="marker-note">
					Darstellung auf {protocol.markers.length} von {protocol.marker_count} Einträgen begrenzt.
				</p>
			{/if}
		</article>
	{/each}
</div>

<footer class="protocol-legend">
	<span><i class="carbs"></i>KH</span>
	<span><i class="rapid"></i>Schnellinsulin</span>
	<span><i class="correction"></i>Korrekturinsulin</span>
	<span><i class="basal"></i>Basalinsulin</span>
	<span><i class="compression"></i>Möglicher Kompressionswert</span>
	<span><i class="change"></i>Einstellungsänderung</span>
	<span>Zahl = Menge (KE bzw. U)</span>
</footer>

<style>
	.protocols {
		display: grid;
		width: 100%;
		min-width: 0;
		max-width: 100%;
		gap: 0.38rem;
	}

	.protocol-panel {
		width: 100%;
		min-width: 0;
		max-width: 100%;
		border-top: 1px solid #bac8cc;
		padding-top: 0.34rem;
	}

	.protocol-panel:first-child {
		border-top: 0;
		padding-top: 0;
	}

	.protocol-header {
		display: flex;
		justify-content: space-between;
		gap: 0.6rem;
		margin-bottom: 0.08rem;
		font-size: 0.73rem;
		color: #18313d;
	}

	.protocol-header span {
		font-size: 0.62rem;
		color: #58707a;
	}

	.trace-scroll {
		width: 100%;
		min-width: 0;
		max-width: 100%;
		overflow-x: auto;
	}

	.trace {
		display: block;
		width: 100%;
		height: auto;
		min-width: 560px;
	}

	.grid,
	.vertical {
		stroke: #d5dfe1;
		stroke-width: 0.7;
		stroke-dasharray: 2 2;
	}

	.threshold {
		stroke: #75a273;
		stroke-width: 1;
		stroke-dasharray: none;
	}

	.axis,
	.unit {
		font-size: 8px;
		fill: #59717a;
	}

	.unit {
		font-size: 7px;
		font-weight: 700;
	}

	.marker-symbol {
		font-size: 4.6px;
		fill: #fff;
		font-weight: 800;
	}

	.marker-value {
		font-size: 6.3px;
		font-weight: 700;
		paint-order: stroke;
		stroke: #fff;
		stroke-width: 1.7px;
		stroke-linejoin: round;
	}

	.ranges-scroll {
		width: 100%;
		min-width: 0;
		max-width: 100%;
		overflow-x: auto;
	}

	.ranges {
		min-width: 560px;
		margin-top: 0.04rem;
		font-size: 0.5rem;
		font-variant-numeric: tabular-nums;
	}

	.range-row {
		display: grid;
		grid-template-columns: 2rem repeat(24, minmax(0, 1fr));
		border-top: 1px solid #dce5e7;
	}

	.range-row > * {
		min-width: 0;
		padding: 0.08rem 0;
		text-align: center;
		border-left: 1px solid #edf1f2;
	}

	.range-row > :first-child {
		border-left: 0;
		text-align: right;
		padding-right: 0.18rem;
		color: #536b75;
	}

	.labels {
		font-size: 0.43rem;
		color: #71838a;
	}

	.outlier {
		background: #f7d6d3;
		color: #9f2118;
		font-weight: 700;
	}

	.high {
		background: #f8e4bd;
		color: #8b5900;
		font-weight: 700;
	}

	.empty {
		color: #9ba9ad;
	}

	.protocol-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.12rem 0.55rem;
		font-size: 0.57rem;
		color: #536b75;
	}

	.marker-note {
		margin: 0.16rem 0 0 2rem;
		font-size: 0.57rem;
		color: #536b75;
	}

	.protocol-legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.18rem;
	}

	.protocol-legend i {
		display: inline-block;
		width: 0.42rem;
		height: 0.42rem;
		border-radius: 99px;
	}

	.protocol-legend {
		margin-top: 0.4rem;
		padding-top: 0.3rem;
		border-top: 1px solid #c6d3d6;
	}

	.carbs {
		background: #b57600;
	}

	.rapid {
		background: #176b87;
	}

	.basal {
		background: #5c4b8a;
	}

	.correction {
		background: #b3261e;
	}

	.protocol-legend .change {
		width: 0;
		height: 0.46rem;
		border-left: 1.3px dashed #596a72;
		border-radius: 0;
	}

	.compression {
		box-sizing: border-box;
		background: #fff;
		border: 1.3px solid #66767c;
	}

	.compression-point {
		fill: #fff;
		stroke: #66767c;
		stroke-width: 1.4;
	}

	.setting-line {
		stroke-width: 0.9;
		stroke-dasharray: 2.5 2;
		opacity: 0.85;
	}

	.setting-label {
		font-size: 5.8px;
		font-weight: 700;
		paint-order: stroke;
		stroke: #fff;
		stroke-width: 2px;
		stroke-linejoin: round;
	}

	@media print {
		.trace-scroll,
		.ranges-scroll {
			overflow: visible !important;
		}

		.protocols {
			gap: 1.2mm;
		}

		.protocol-panel {
			padding-top: 1.1mm;
		}

		.trace {
			min-width: 0;
		}

		.ranges {
			min-width: 0;
			font-size: 4.7pt;
		}

		.marker-note,
		.protocol-legend {
			font-size: 5.2pt;
		}

		.protocol-legend {
			flex-wrap: nowrap;
			min-height: 3.2mm;
			padding-top: 0;
			line-height: 3.2mm;
			overflow-x: clip;
			overflow-y: visible;
		}

		.protocol-legend span {
			flex: 0 0 auto;
			white-space: nowrap;
		}
	}
</style>
