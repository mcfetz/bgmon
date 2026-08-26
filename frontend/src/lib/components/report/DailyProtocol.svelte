<script lang="ts">
	import type { DayProtocol, GlucosePoint, LogMarker } from '$lib/api/report';
	import { clampGlucose, glucoseTrace, timeOfDayMinutes, type GlucoseTrace } from './chart';

	let {
		protocols,
		readingsByDate
	}: {
		protocols: DayProtocol[];
		readingsByDate: ReadonlyMap<string, GlucosePoint[]>;
	} = $props();

	const width = 850;
	const height = 105;
	const pad = { top: 14, right: 14, bottom: 21, left: 30 };
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
		if (marker.kind === 'basal') return '#5c4b8a';
		return '#596a72';
	}

	function markerTitle(marker: LogMarker): string {
		const kind =
			marker.kind === 'carbs'
				? 'Kohlenhydrate'
				: marker.kind === 'rapid_insulin'
					? 'Schnellinsulin'
					: marker.kind === 'basal'
						? 'Basalinsulin'
						: 'Notiz';
		const value = `${marker.value}${marker.unit}`;
		return [marker.timestamp, kind, value, marker.notes?.trim()].filter(Boolean).join(' · ');
	}

	function truncate(value: string, maximumLength: number): string {
		return value.length > maximumLength ? `${value.slice(0, maximumLength - 3)}...` : value;
	}

	function markerSummary(marker: LogMarker): string {
		if (marker.kind === 'carbs') return `KH ${marker.value}${marker.unit}`;
		if (marker.kind === 'rapid_insulin') return `Schnell ${marker.value}${marker.unit}`;
		if (marker.kind === 'basal') return `Basal ${marker.value}${marker.unit}`;
		return `Notiz ${truncate(marker.notes?.trim() || 'ohne Text', 26)}`;
	}

	function markerSymbol(marker: LogMarker): string {
		if (marker.kind === 'carbs') return 'KH';
		if (marker.kind === 'rapid_insulin') return 'S';
		if (marker.kind === 'basal') return 'B';
		return 'N';
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
		{@const markerSummaries = protocol.markers.slice(0, 4)}
		{@const undisplayedMarkerCount = Math.max(0, protocol.marker_count - markerSummaries.length)}
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
					{#each protocol.markers as marker}
						<g
							transform={`translate(${xScale(timeOfDayMinutes(marker.timestamp))} ${pad.top + 8})`}
						>
							<title>{markerTitle(marker)}</title>
							<circle r="5.2" fill={markerColor(marker)} stroke="#fff" stroke-width="1" />
							<text y="2.3" text-anchor="middle" class="marker-symbol">{markerSymbol(marker)}</text>
						</g>
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
			{#if protocol.markers.length > 0}
				<div class="marker-summary" aria-label={`Protokollierte Marker ${protocol.date}`}>
					{#each markerSummaries as marker}
						<span class="summary-marker" title={markerTitle(marker)}
							><i style={`background: ${markerColor(marker)}`}></i>{markerSummary(marker)}</span
						>
					{/each}
					{#if undisplayedMarkerCount > 0}
						<span class="more-markers">+ {undisplayedMarkerCount} weitere</span>
					{/if}
					{#if protocol.markers_truncated}
						<span class="more-markers" title="Marker-Darstellung wurde begrenzt"
							>Darstellung begrenzt</span
						>
					{/if}
				</div>
			{/if}
		</article>
	{/each}
</div>

<footer class="protocol-legend">
	<span><i class="carbs"></i>KH</span>
	<span><i class="rapid"></i>Schnellinsulin</span>
	<span><i class="basal"></i>Basalinsulin</span>
	<span><i class="note"></i>Notiz</span>
	<span><i class="compression"></i>Möglicher Kompressionswert</span>
	<span>Marker zeigen nur protokollierte Einträge.</span>
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
		font-size: 5px;
		fill: #fff;
		font-weight: 800;
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

	.marker-summary {
		display: flex;
		align-items: center;
		gap: 0.12rem 0.4rem;
		height: 0.78rem;
		margin: 0.16rem 0 0 2rem;
		overflow: hidden;
		font-size: 0.57rem;
		line-height: 0.78rem;
		color: #536b75;
	}

	.summary-marker {
		display: inline-flex;
		flex: 1 1 0;
		min-width: 0;
		align-items: center;
		gap: 0.18rem;
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.more-markers {
		flex: 0 0 auto;
		white-space: nowrap;
	}

	.protocol-legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.18rem;
	}

	.marker-summary i,
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

	.note {
		background: #596a72;
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

		.marker-summary,
		.protocol-legend {
			font-size: 5.2pt;
		}

		.marker-summary {
			height: 2.8mm;
			line-height: 2.8mm;
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
