<script lang="ts">
	import type { GlucoseReading, LogEntryReading, PredictionPoint } from '$lib/api/dashboard';

	let {
		readings = [] as GlucoseReading[],
		logs = [] as readonly LogEntryReading[],
		criticalLow = 54,
		low = 70,
		high = 180,
		criticalHigh = 250,
		insulinActionHours = 4,
		onswipe = ((_ratio: number) => {}) as (ratio: number) => void,
		highlightedTimestamp = null as string | null,
		predictions30 = [] as PredictionPoint[],
		predictions60 = [] as PredictionPoint[],
		windowStart = null as Date | null,
		windowEnd = new Date() as Date,
		windowLabel = '',
		logFilters = { carbs: true, insulin: true, basal: true, alarm: false, note: true } as Record<string, boolean>,
		historyPredictions30 = [] as PredictionPoint[],
		historyPredictions60 = [] as PredictionPoint[],
		historyPredictions120 = [] as PredictionPoint[]
	} = $props();

	const width = 600;
	const height = 250;
	const pad = { top: 20, right: 20, bottom: 40, left: 20 };

	function zoneColor(value: number): string {
		if (value <= criticalLow) return '#ef4444';
		if (value <= low) return '#f97316';
		if (value >= criticalHigh) return '#ef4444';
		if (value >= high) return '#eab308';
		return '#22c55e';
	}

	// Parse timestamps
	const timePoints = $derived(
		readings
			.filter((r) => r.sgv != null && r.timestamp)
			.map((r) => ({
				sgv: r.sgv!,
				trend: r.trend,
				direction: r.direction,
				ts: new Date(r.timestamp!).getTime(),
				timestamp: r.timestamp
			}))
			.sort((a, b) => a.ts - b.ts)
	);

	const plotWidth = $derived(width - pad.left - pad.right);
	const plotHeight = $derived(height - pad.top - pad.bottom);

	const showPredictions = $derived(
		Math.abs(windowEnd.getTime() - Date.now()) < 10 * 60 * 1000
	);

	const timeRange = $derived.by(() => {
		let min = windowStart?.getTime() ?? (timePoints.length > 0 ? timePoints[0].ts : null);
		let max = windowEnd.getTime();

		if (showPredictions) {
			function extendTime(pts: PredictionPoint[]) {
				for (const p of pts) {
					const ts = new Date(p.timestamp).getTime();
					if (min === null || ts < min) min = ts;
					if (max === null || ts > max) max = ts;
				}
			}
			extendTime(predictions30);
			extendTime(predictions60);
		}

		return min !== null ? { min, max } : null;
	});

	const minY = $derived(
		timePoints.length > 0 ? Math.min(low - 20, ...timePoints.map((p) => p.sgv), 40) : 40
	);
	const maxY = $derived(
		timePoints.length > 0 ? Math.max(high + 20, ...timePoints.map((p) => p.sgv)) : 250
	);

	function xPos(ts: number): number {
		if (!timeRange) return pad.left;
		const ratio = (ts - timeRange.min) / (timeRange.max - timeRange.min);
		return pad.left + ratio * plotWidth;
	}

	function yPos(v: number): number {
		return pad.top + plotHeight - ((v - minY) / (maxY - minY)) * plotHeight;
	}

	// X-axis ticks
	const xTicks = $derived(() => {
		if (!timeRange) return [];
		const rangeStart = timeRange.min;
		const rangeEnd = timeRange.max;
		const spanMs = rangeEnd - rangeStart;
		const spanHours = spanMs / (3600 * 1000);

		let intervalMs: number;
		if (spanHours <= 2) intervalMs = 30 * 60 * 1000;
		else if (spanHours <= 6) intervalMs = 60 * 60 * 1000;
		else if (spanHours <= 12) intervalMs = 2 * 60 * 60 * 1000;
		else if (spanHours <= 24) intervalMs = 3 * 60 * 60 * 1000;
		else if (spanHours <= 48) intervalMs = 6 * 60 * 60 * 1000;
		else if (spanHours <= 7 * 24) intervalMs = 24 * 60 * 60 * 1000;
		else intervalMs = 48 * 60 * 60 * 1000;

		const ticks = [];
		const startTick = Math.floor(rangeStart / intervalMs) * intervalMs;
		for (let t = startTick; t <= rangeEnd; t += intervalMs) {
			if (t >= rangeStart) {
				ticks.push({
					x: xPos(t),
					label:
						spanHours > 24
							? new Date(t).toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit' })
							: new Date(t).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }),
					isDayStart: new Date(t).getHours() === 0 && new Date(t).getMinutes() === 0
				});
			}
		}
		return ticks;
	});

	// Day boundary lines
	const dayBoundaries = $derived(() => {
		if (!timeRange || timePoints.length < 2) return [];
		const boundaries = [];
		let prevDate = new Date(timePoints[0].ts).toDateString();
		for (let i = 1; i < timePoints.length; i++) {
			const currDate = new Date(timePoints[i].ts).toDateString();
			if (currDate !== prevDate) {
				const boundaryTs = timePoints[i].ts;
				boundaries.push(xPos(boundaryTs));
				prevDate = currDate;
			}
		}
		return boundaries;
	});

	// Line path using time-based x positions
	const linePath = $derived(
		timePoints.length > 0
			? timePoints.map((p, i) => `${i === 0 ? 'M' : 'L'}${xPos(p.ts)},${yPos(p.sgv)}`).join(' ')
			: ''
	);

	let historyFilterOpen = $state(false);
	let showHistory30 = $state(false);
	let showHistory60 = $state(true);
	let showHistory120 = $state(false);

	const HISTORY_COLORS: Record<number, string> = { 30: '#3b82f6', 60: '#8b5cf6', 120: '#f59e0b' };

	function _historyPath(pts: PredictionPoint[]): string {
		const mapped = pts
			.map((p) => ({ ts: new Date(p.timestamp).getTime(), sgv: p.predicted_sgv }))
			.filter((p) => !isNaN(p.ts) && p.sgv != null)
			.sort((a, b) => a.ts - b.ts);
		if (mapped.length < 2) return '';
		return mapped.map((p, i) => `${i === 0 ? 'M' : 'L'}${xPos(p.ts)},${yPos(p.sgv)}`).join(' ');
	}

	const historyPath30 = $derived(showHistory30 ? _historyPath(historyPredictions30) : '');
	const historyPath60 = $derived(showHistory60 ? _historyPath(historyPredictions60) : '');
	const historyPath120 = $derived(showHistory120 ? _historyPath(historyPredictions120) : '');

	const dots = $derived(
		timePoints.map((p) => ({
			cx: xPos(p.ts),
			cy: yPos(p.sgv),
			color: zoneColor(p.sgv),
			value: p.sgv,
			timestamp: p.timestamp
		}))
	);

	function computeForecast(pts: PredictionPoint[]) {
		const points = pts
			.filter((p) => p.predicted_sgv != null)
			.map((p) => ({
				ts: new Date(p.timestamp).getTime(),
				sgv: p.predicted_sgv,
				lower: p.lower_bound,
				upper: p.upper_bound,
				timestamp: p.timestamp
			}))
			.sort((a, b) => a.ts - b.ts);

		const linePath =
			points.length > 0
				? points.map((p, i) => `${i === 0 ? 'M' : 'L'}${xPos(p.ts)},${yPos(p.sgv)}`).join(' ')
				: '';

		let bandPath = '';
		if (points.length >= 2) {
			const upper = points.map((p) => `${xPos(p.ts)},${yPos(p.upper ?? p.sgv)}`).join(' L');
			const lower = [...points]
				.reverse()
				.map((p) => `${xPos(p.ts)},${yPos(p.lower ?? p.sgv)}`)
				.join(' L');
			bandPath = `M${upper} L${lower} Z`;
		}

		const terminalDot =
			points.length > 0
				? {
						cx: xPos(points[points.length - 1].ts),
						cy: yPos(points[points.length - 1].sgv),
						value: points[points.length - 1].sgv,
						timestamp: points[points.length - 1].timestamp
					}
				: null;

		return { linePath, bandPath, terminalDot };
	}

	const forecast30 = $derived(computeForecast(predictions30));
	const forecast60 = $derived(computeForecast(predictions60));

	const combinedPredLine = $derived.by(() => {
		if (!showPredictions) return '';
		if (readings.length === 0) return '';
		const last = readings[readings.length - 1];
		if (!last || last.sgv == null || !last.timestamp) return '';

		const lx = xPos(new Date(last.timestamp).getTime());
		const ly = yPos(last.sgv);

		const p30 = predictions30.length > 0 ? predictions30[predictions30.length - 1] : null;
		const p60 = predictions60.length > 0 ? predictions60[predictions60.length - 1] : null;

		if (!p30 || p30.predicted_sgv == null) return '';
		const x30 = xPos(new Date(p30.timestamp).getTime());
		const y30 = yPos(p30.predicted_sgv);

		if (!p60 || p60.predicted_sgv == null) return '';
		const x60 = xPos(new Date(p60.timestamp).getTime());
		const y60 = yPos(p60.predicted_sgv);

		return `M${lx},${ly} L${x30},${y30} L${x60},${y60}`;
	});

	const combinedBand = $derived.by(() => {
		if (!showPredictions || readings.length === 0) return '';
		const last = readings[readings.length - 1];
		if (!last || last.sgv == null || !last.timestamp) return '';

		const lx = xPos(new Date(last.timestamp).getTime());
		const ly = yPos(last.sgv);

		const p30 = predictions30.length > 0 ? predictions30[predictions30.length - 1] : null;
		const p60 = predictions60.length > 0 ? predictions60[predictions60.length - 1] : null;

		if (!p30 || p30.predicted_sgv == null) return '';
		const x30 = xPos(new Date(p30.timestamp).getTime());
		const lo30 = yPos(p30.lower_bound ?? p30.predicted_sgv);
		const up30 = yPos(p30.upper_bound ?? p30.predicted_sgv);

		if (!p60 || p60.predicted_sgv == null) return '';
		const x60 = xPos(new Date(p60.timestamp).getTime());
		const lo60 = yPos(p60.lower_bound ?? p60.predicted_sgv);
		const up60 = yPos(p60.upper_bound ?? p60.predicted_sgv);

		return `M${lx},${ly} L${x30},${lo30} L${x60},${lo60} L${x60},${up60} L${x30},${up30} Z`;
	});

	const highlightX = $derived.by(() => {
		if (!highlightedTimestamp || !timeRange) return null;
		const ts = new Date(highlightedTimestamp).getTime();
		if (ts < timeRange.min || ts > timeRange.max) return null;
		return xPos(ts);
	});

	// Log markers positioned just above x-axis
	const logMarkers = $derived(() => {
		if (!timeRange || logs.length === 0) return [];
		const markerY = height - pad.bottom - 10;
		return logs
			.filter((log) => {
				if (log.entry_type === 'carbs') return logFilters.carbs;
				if (log.entry_type === 'insulin') return logFilters.insulin;
				if (log.entry_type === 'basal') return logFilters.basal;
				if (log.entry_type === 'alarm') return logFilters.alarm;
				if (log.entry_type === 'note' || log.entry_type === 'success') return logFilters.note;
				return true;
			})
			.filter((l) => l.created_at)
			.map((l) => {
				const ts = new Date(l.created_at).getTime();
				if (ts < timeRange.min || ts > timeRange.max) return null;
				return {
					x: xPos(ts),
					y: markerY,
					type: l.entry_type,
					value: l.value,
					unit: l.unit,
					notes: l.notes,
					timestamp: l.created_at
				};
			})
			.filter((m): m is NonNullable<typeof m> => m !== null);
	});

	// Insulin action windows (4h after each insulin entry)
	const insulinWindows = $derived(() => {
		if (!timeRange || logs.length === 0) return [];
		const windows = logs
			.filter((l) => l.entry_type === 'insulin' && l.created_at)
			.map((l) => {
				const startTs = new Date(l.created_at).getTime();
				const endTs = startTs + insulinActionHours * 60 * 60 * 1000;
				console.log('Insulin window:', {
					startTs,
					endTs,
					timeRange,
					diff: (endTs - startTs) / 3600000
				});
				// Only show if window overlaps with visible time range
				if (endTs < timeRange.min || startTs > timeRange.max) return null;
				const x1 = Math.max(xPos(startTs), pad.left);
				const x2 = Math.min(xPos(endTs), width - pad.right);
				return {
					x: x1,
					width: x2 - x1,
					value: l.value,
					unit: l.unit,
					timestamp: l.created_at
				};
			})
			.filter((w): w is NonNullable<typeof w> => w !== null && w.width > 0);
		console.log('Insulin windows:', windows);
		return windows;
	});

	// Tooltip
	let tooltip = $state<{
		clientX: number;
		clientY: number;
		value: number;
		timestamp: string | null;
		label?: string;
	} | null>(null);
	let containerEl: HTMLDivElement | null = null;

	function showTooltip(dot: (typeof dots)[0], event: MouseEvent) {
		tooltip = {
			clientX: event.clientX,
			clientY: event.clientY,
			value: dot.value,
			timestamp: dot.timestamp
		};
	}

	function showLogTooltip(marker: ReturnType<typeof logMarkers>[number], event: MouseEvent) {
		const typeLabels: Record<string, string> = { carbs: 'KE', insulin: 'Insulin', basal: 'Basal' };
		tooltip = {
			clientX: event.clientX,
			clientY: event.clientY,
			value: marker.value,
			timestamp: marker.timestamp,
			label: `${typeLabels[marker.type] ?? marker.type}: ${marker.value} ${marker.unit}`
		};
	}

	function hideTooltip() {
		tooltip = null;
	}

	function formatTime(timestamp: string | null): string {
		if (!timestamp) return '';
		const d = new Date(timestamp);
		return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
	}

	function tooltipStyle(): string {
		if (!tooltip || !containerEl) return 'display: none;';
		const rect = containerEl.getBoundingClientRect();
		const tooltipWidth = 140;
		const tooltipHeight = 50;
		let left = tooltip.clientX - rect.left + 12;
		let top = tooltip.clientY - rect.top - tooltipHeight - 8;
		if (left + tooltipWidth > rect.width) left = tooltip.clientX - rect.left - tooltipWidth - 12;
		if (top < 0) top = tooltip.clientY - rect.top + 12;
		return `left: ${left}px; top: ${top}px;`;
	}

	function onMouseMove(event: MouseEvent) {
		if (tooltip) {
			tooltip = {
				clientX: event.clientX,
				clientY: event.clientY,
				value: tooltip.value,
				timestamp: tooltip.timestamp,
				label: tooltip.label
			};
		}
	}

	// Touch swipe support
	let touchStartX = $state<number | null>(null);
	let touchStartY = $state<number | null>(null);
	let touchCurrentX = $state<number | null>(null);
	let swipeOffset = $derived(
		touchStartX !== null && touchCurrentX !== null ? touchCurrentX - touchStartX : 0
	);

	function onTouchStart(event: TouchEvent) {
		if (event.touches.length !== 1) return;
		touchStartX = event.touches[0].clientX;
		touchStartY = event.touches[0].clientY;
		touchCurrentX = touchStartX;
	}

	function onTouchMove(event: TouchEvent) {
		if (touchStartX === null || event.touches.length !== 1) return;
		touchCurrentX = event.touches[0].clientX;
		const dy = Math.abs(event.touches[0].clientY - (touchStartY ?? 0));
		if (dy < 30) event.preventDefault();
	}

	function onTouchEnd() {
		if (touchStartX === null || touchCurrentX === null) return;
		const dx = touchCurrentX - touchStartX;
		const threshold = containerEl ? containerEl.clientWidth * 0.15 : 50;
		if (Math.abs(dx) >= threshold && containerEl) {
			const ratio = Math.min(Math.abs(dx) / containerEl.clientWidth, 1);
			onswipe(dx < 0 ? ratio : -ratio);
		}
		touchStartX = null;
		touchStartY = null;
		touchCurrentX = null;
	}

	function markerColor(type: string): string {
		const colors: Record<string, string> = {
			carbs: '#3b82f6',
			insulin: '#a855f7',
			basal: '#f97316'
		};
		return colors[type] ?? '#94a3b8';
	}
</script>

<div class="graph-wrapper" bind:this={containerEl} role="img" aria-label="Glucose chart">
	<button
		class="nav-zone nav-zone-left"
		type="button"
		onclick={() => onswipe(-1)}
		aria-label="Zurück in der Zeit">‹</button
	>
	<button
		class="nav-zone nav-zone-right"
		type="button"
		onclick={() => onswipe(1)}
		aria-label="Vor in der Zeit">›</button
	>
	<div
		class="graph-container"
		class:swiping={touchStartX !== null}
		style="transform: translateX({swipeOffset * 0.3}px)"
		onmousemove={onMouseMove}
		ontouchstart={onTouchStart}
		ontouchmove={onTouchMove}
		ontouchend={onTouchEnd}
		ontouchcancel={onTouchEnd}
	>
		{#if windowLabel}
			<div class="window-label">
				<span>{windowLabel}</span>
				<button
					class="history-filter-btn"
					type="button"
					onclick={() => (historyFilterOpen = !historyFilterOpen)}
					aria-label="Prognose-Verlauf einstellen"
				>
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M4 21v-7M4 10V3M12 21v-5M12 12V3M20 21v-3M20 14V3" />
						<circle cx="4" cy="14" r="2" fill="currentColor" />
						<circle cx="12" cy="16" r="2" fill="currentColor" />
						<circle cx="20" cy="18" r="2" fill="currentColor" />
					</svg>
				</button>
				{#if historyFilterOpen}
					<div class="history-filter-popup">
						{#each [30, 60, 120] as h}
							{@const checked = h === 30 ? showHistory30 : h === 60 ? showHistory60 : showHistory120}
							{@const onChange = h === 30
								? () => (showHistory30 = !showHistory30)
								: h === 60
									? () => (showHistory60 = !showHistory60)
									: () => (showHistory120 = !showHistory120)}
							<label class="history-filter-item">
								<span class="history-filter-item-label">
									<span class="history-color-dot" style="background:{HISTORY_COLORS[h]}"></span>
									{h} min Prognose
								</span>
								<input type="checkbox" checked={checked} onchange={onChange} />
							</label>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
		<svg {width} {height} viewBox="0 0 {width} {height}">
			<!-- Threshold zones -->
			<rect
				x={pad.left}
				y={yPos(criticalHigh)}
				width={plotWidth}
				height={yPos(high) - yPos(criticalHigh)}
				fill="#ef4444"
				opacity="0.06"
			/>
			<rect
				x={pad.left}
				y={yPos(high)}
				width={plotWidth}
				height={yPos(low) - yPos(high)}
				fill="#22c55e"
				opacity="0.06"
			/>
			<rect
				x={pad.left}
				y={yPos(low)}
				width={plotWidth}
				height={yPos(criticalLow) - yPos(low)}
				fill="#f97316"
				opacity="0.06"
			/>
			<rect
				x={pad.left}
				y={yPos(criticalLow)}
				width={plotWidth}
				height={yPos(minY) - yPos(criticalLow)}
				fill="#ef4444"
				opacity="0.06"
			/>

			<!-- Insulin action windows (4h) -->
			{#each insulinWindows() as window}
				<rect
					x={window.x}
					y={pad.top}
					width={window.width}
					height={plotHeight}
					fill="#a855f7"
					opacity="0.12"
					rx="4"
				/>
			{/each}

			<!-- Day boundary lines -->
			{#each dayBoundaries() as x}
				<line
					x1={x}
					y1={pad.top}
					x2={x}
					y2={height - pad.bottom}
					stroke="#94a3b8"
					stroke-dasharray="2,4"
					stroke-width="1"
					opacity="0.3"
				/>
			{/each}

			<!-- Threshold lines -->
			{#each [{ y: criticalHigh, color: '#ef4444' }, { y: high, color: '#eab308' }, { y: low, color: '#f97316' }, { y: criticalLow, color: '#ef4444' }] as line}
				<line
					x1={pad.left}
					y1={yPos(line.y)}
					x2={width - pad.right}
					y2={yPos(line.y)}
					stroke={line.color}
					stroke-dasharray="4,3"
					stroke-width="1"
					opacity="0.4"
				/>
				<text
					x={pad.left + 6}
					y={yPos(line.y) <= pad.top + 12 ? yPos(line.y) + 13 : yPos(line.y) - 3}
					text-anchor="start"
					fill={line.color}
					font-size="11"
					opacity="0.7">{line.y}</text
				>
			{/each}

			{#if highlightX !== null}
				<line
					x1={highlightX}
					y1={pad.top}
					x2={highlightX}
					y2={height - pad.bottom}
					stroke="var(--color-primary)"
					stroke-width="2"
					stroke-dasharray="3,3"
					opacity="0.7"
				/>
			{/if}

			<!-- Glucose line -->
			{#if linePath}
				<path d={linePath} fill="none" stroke="var(--color-primary)" stroke-width="2" />
			{/if}

			<!-- Historical predictions (colored lines) -->
			{#if historyPath30}
				<path d={historyPath30} fill="none" stroke={HISTORY_COLORS[30]} stroke-width="1.5" stroke-dasharray="3,6" opacity="0.4" />
			{/if}
			{#if historyPath60}
				<path d={historyPath60} fill="none" stroke={HISTORY_COLORS[60]} stroke-width="1.5" stroke-dasharray="3,6" opacity="0.4" />
			{/if}
			{#if historyPath120}
				<path d={historyPath120} fill="none" stroke={HISTORY_COLORS[120]} stroke-width="1.5" stroke-dasharray="3,6" opacity="0.4" />
			{/if}

			<!-- Combined prediction band (last BG → 30min CI → 60min CI) -->
			{#if combinedBand}
				<path d={combinedBand} fill="#8b5cf6" opacity="0.12" />
			{/if}

			<!-- Combined prediction line (last BG → 30min → 60min) -->
			{#if combinedPredLine}
				<path
					d={combinedPredLine}
					fill="none"
					stroke="#8b5cf6"
					stroke-width="2.5"
					stroke-dasharray="6,4"
					opacity="0.7"
				/>
			{/if}

			<!-- Terminal dots -->
			{#if showPredictions && forecast30.terminalDot}
				<circle cx={forecast30.terminalDot.cx} cy={forecast30.terminalDot.cy}
					r="4" fill="#8b5cf6" opacity="0.8" />
			{/if}
			{#if showPredictions && forecast60.terminalDot}
				<circle cx={forecast60.terminalDot.cx} cy={forecast60.terminalDot.cy}
					r="4" fill="#8b5cf6" opacity="0.8" />
			{/if}

			<!-- Data dots -->
			{#each dots as dot, i}
				<circle
					cx={dot.cx}
					cy={dot.cy}
					r={i === dots.length - 1 ? 6 : 3}
					fill={dot.color}
					opacity={i === dots.length - 1 ? 1 : 0.7}
					class="data-dot"
					onmouseenter={(e) => showTooltip(dot, e)}
					onmouseleave={hideTooltip}
				/>
			{/each}

			<!-- Log markers -->
			{#each logMarkers() as marker}
				{#if marker.type === 'carbs'}
					<!-- Triangle pointing up -->
					<polygon
						points="{marker.x},{marker.y - 6} {marker.x - 5},{marker.y + 4} {marker.x +
							5},{marker.y + 4}"
						fill={markerColor(marker.type)}
						class="log-marker"
						onmouseenter={(e) => showLogTooltip(marker, e)}
						onmouseleave={hideTooltip}
					/>
				{:else if marker.type === 'insulin'}
					<!-- Diamond -->
					<polygon
						points="{marker.x},{marker.y - 5} {marker.x + 5},{marker.y} {marker.x},{marker.y +
							5} {marker.x - 5},{marker.y}"
						fill={markerColor(marker.type)}
						class="log-marker"
						onmouseenter={(e) => showLogTooltip(marker, e)}
						onmouseleave={hideTooltip}
					/>
				{:else}
					<!-- Square for basal -->
					<rect
						x={marker.x - 4}
						y={marker.y - 4}
						width="8"
						height="8"
						fill={markerColor(marker.type)}
						class="log-marker"
						onmouseenter={(e) => showLogTooltip(marker, e)}
						onmouseleave={hideTooltip}
					/>
				{/if}
			{/each}

			<!-- X-axis line -->
			<line
				x1={pad.left}
				y1={height - pad.bottom}
				x2={width - pad.right}
				y2={height - pad.bottom}
				stroke="#475569"
				stroke-width="1"
			/>

			<!-- X-axis ticks -->
			{#each xTicks() as tick}
				<line
					x1={tick.x}
					y1={height - pad.bottom}
					x2={tick.x}
					y2={height - pad.bottom + 4}
					stroke="#475569"
					stroke-width="1"
				/>
			{/each}
		</svg>
		{#if xTicks().length > 0}
			<div class="x-axis-labels" aria-label="Zeitachse">
				{#each xTicks() as tick}
					<span>{tick.label}</span>
				{/each}
			</div>
		{/if}
		<!-- Tooltip -->
		{#if tooltip}
			<div class="tooltip" style={tooltipStyle()}>
				{#if tooltip.label}
					<div class="tooltip-label">{tooltip.label}</div>
				{:else}
					<div class="tooltip-value">{tooltip.value} mg/dL</div>
				{/if}
				<div class="tooltip-time">{formatTime(tooltip.timestamp)}</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.graph-wrapper {
		position: relative;
		width: 100%;
	}

	.nav-zone {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 48px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 2rem;
		font-weight: 300;
		color: var(--color-text-muted);
		background: transparent;
		border: none;
		cursor: pointer;
		z-index: 2;
		opacity: 0;
		transition:
			opacity 0.2s,
			background 0.15s;
		-webkit-appearance: none;
		appearance: none;
		outline: none;
		padding: 0;
	}

	.nav-zone:hover,
	.nav-zone:focus-visible {
		opacity: 0.6;
		background: rgba(var(--color-primary-rgb), 0.1);
		outline: none;
	}

	.nav-zone:active {
		background: rgba(var(--color-primary-rgb), 0.2);
	}

	@media (hover: none) {
		.nav-zone {
			opacity: 0.25;
		}

		.nav-zone:active {
			opacity: 0.6;
		}
	}

	.nav-zone-left {
		left: 0;
		border-radius: var(--radius) 0 0 var(--radius);
	}

	.nav-zone-right {
		right: 0;
		border-radius: 0 var(--radius) var(--radius) 0;
	}

	.graph-container {
		width: 100%;
		overflow-x: auto;
		overscroll-behavior-x: none;
		background: var(--color-surface);
		border-radius: var(--radius);
		padding: var(--spacing-md);
		position: relative;
	}

	.window-label {
		margin-top: 0;
		color: var(--color-text-muted);
		font-size: 0.875rem;
		font-variant-numeric: tabular-nums;
		text-align: center;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		position: relative;
		padding: 0 12px;
	}

	.window-label > span {
		flex: 1;
	}

	.history-filter-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 2px;
		display: flex;
		align-items: center;
		opacity: 0.6;
		transition: opacity 0.15s;
		margin-left: auto;
	}

	.history-filter-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 2px;
		display: flex;
		align-items: center;
		opacity: 0.6;
		transition: opacity 0.15s;
	}

	.history-filter-btn:hover {
		opacity: 1;
		color: var(--color-text);
	}

	.history-filter-popup {
		position: absolute;
		top: 100%;
		right: 0;
		margin-top: 4px;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: var(--spacing-sm);
		z-index: 50;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
		min-width: 140px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.history-filter-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		font-size: 0.8rem;
		color: var(--color-text);
		cursor: pointer;
		padding: 3px 4px;
		border-radius: 4px;
	}

	.history-filter-item-label {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.history-filter-item:hover {
		background: var(--color-bg);
	}

	.history-filter-item input[type='checkbox'] {
		accent-color: var(--color-primary);
	}

	.history-color-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.graph-container.swiping {
		transition: none;
	}

	svg {
		display: block;
		width: 100%;
		height: auto;
	}

	.x-axis-labels {
		display: flex;
		justify-content: space-between;
		gap: var(--spacing-sm);
		padding: 0 var(--spacing-sm);
		color: var(--color-text-muted);
		font-size: 0.875rem;
		font-variant-numeric: tabular-nums;
		line-height: 1.25;
	}

	.x-axis-labels span {
		white-space: nowrap;
	}

	.data-dot {
		cursor: crosshair;
		transition: r 0.15s ease;
	}

	.data-dot:hover {
		r: 7;
		stroke: white;
		stroke-width: 2;
	}

	.log-marker {
		cursor: pointer;
		transition: opacity 0.15s ease;
		opacity: 0.85;
	}

	.log-marker:hover {
		opacity: 1;
		stroke: white;
		stroke-width: 1.5;
	}

	.tooltip {
		position: absolute;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: var(--spacing-xs) var(--spacing-sm);
		pointer-events: none;
		z-index: 10;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
		white-space: nowrap;
	}

	.tooltip-value {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-text);
	}

	.tooltip-label {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-text);
	}

	.tooltip-time {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}
</style>
