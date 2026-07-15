<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import GlucoseGraph from '$lib/components/GlucoseGraph.svelte';
	import LogEntryForm from '$lib/components/LogEntryForm.svelte';
	import LogHistory from '$lib/components/LogHistory.svelte';
	import ProfileSelector from '$lib/components/ProfileSelector.svelte';
	import SettingsDialog from '$lib/components/SettingsDialog.svelte';
	import SnoozeIndicator from '$lib/components/SnoozeIndicator.svelte';
	import BgModal from '$lib/components/BgModal.svelte';
	import StatsCard from '$lib/components/StatsCard.svelte';
	import {
		fetchCurrent,
		fetchHistoryRange,
		fetchLogsRange,
		fetchStatsRange,
		fetchThresholds,
		fetchGlobalSettings,
		fetchPrediction
	} from '$lib/api/dashboard';
	import type {
		GlucoseReading,
		LogEntryReading,
		PredictionPoint,
		PredictionResponse,
		StatsData
	} from '$lib/api/dashboard';

	let current = $state<{ sgv: number | null; direction: string | null } | null>(null);
	let readings = $state<GlucoseReading[]>([]);
	let logs = $state<LogEntryReading[]>([]);
	let stats = $state<StatsData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let lastUpdate = $state<string | null>(null);
	let previousSgv = $state<number | null>(null);
	let pulsing = $state(false);
	let now = $state(Date.now());
	let health = $state<{ libre: boolean }>({ libre: false });
	let thresholds = $state<{
		critical_low: number;
		low: number;
		high: number;
		critical_high: number;
	}>({
		critical_low: 54,
		low: 70,
		high: 180,
		critical_high: 250
	});
	let insulinActionHours = $state(4);
	let logRefreshTrigger = $state(0);
	let bgModalOpen = $state(false);
	let highlightedTimestamp = $state<string | null>(null);
	let predictionStatus = $state<
		'idle' | 'ready' | 'disabled' | 'unavailable' | 'insufficient_context'
	>('idle');
	let predictionPoints60 = $state<PredictionPoint[]>([]);
	let predictionPoints30 = $state<PredictionPoint[]>([]);
	let predictionPoints120 = $state<PredictionPoint[]>([]);
	let modelMae30 = $state<number | null>(null);
	let modelMae60 = $state<number | null>(null);
	let modelMae120 = $state<number | null>(null);
	let modelVersion = $state('');
	let appVersion = $state(localStorage.getItem('bgmon_version') || '');
	let newVersionAvailable = $state(false);
	let newVersionDismissed = $state(false);

	let reloading = $state(false);
	async function handleVersionReload() {
		if (reloading) return;
		reloading = true;
		// Store new version before reload so banner stays hidden
		appVersion = localStorage.getItem('bgmon_version_pending') || appVersion;
		localStorage.setItem('bgmon_version', appVersion);
		localStorage.removeItem('bgmon_version_pending');
		try {
			const registration = await navigator.serviceWorker?.ready;
			if (registration) {
				await registration.update();
			}
		} catch {}
		window.location.replace('/?v=' + Date.now());
	}

	async function checkVersion() {
		try {
			const res = await fetch('/api/version');
			if (res.ok) {
				const data = await res.json();
				const v = data.version;
				if (!appVersion) {
					appVersion = v;
					localStorage.setItem('bgmon_version', v);
				} else if (v !== appVersion) {
					localStorage.setItem('bgmon_version_pending', v);
					newVersionAvailable = true;
				}
			}
		} catch {}
	}

	// Time window state
	const initialWindowDurationMs = 3600 * 1000; // default 1h
	let windowDurationMs = $state(initialWindowDurationMs);
	let windowEnd = $state<Date>(new Date());
	let windowStart = $state<Date>(new Date(Date.now() - initialWindowDurationMs));

	const durationButtons = [
		{ label: '-1h', ms: 3600 * 1000 },
		{ label: '-6h', ms: 6 * 3600 * 1000 },
		{ label: '-12h', ms: 12 * 3600 * 1000 },
		{ label: '-1t', ms: 24 * 3600 * 1000 },
		{ label: '-1w', ms: 7 * 24 * 3600 * 1000 }
	];

	function setDuration(ms: number) {
		windowDurationMs = ms;
		const now = Date.now();
		windowEnd = new Date(now);
		windowStart = new Date(now - ms);
		loadDashboard();
	}

	function jumpToNow() {
		const now = Date.now();
		windowEnd = new Date(now);
		windowStart = new Date(now - windowDurationMs);
		loadDashboard();
	}

	function shiftWindow(direction: number) {
		const shift = windowDurationMs * direction;
		const now = Date.now();
		let newEnd = windowEnd.getTime() + shift;
		if (newEnd > now) newEnd = now;
		windowEnd = new Date(newEnd);
		windowStart = new Date(newEnd - windowDurationMs);
		loadDashboard();
	}

	async function loadDashboard() {
		loading = true;
		error = null;
		try {
			const startIso = windowStart.toISOString();
			const endIso = windowEnd.toISOString();
			const [cur, hist, logEntries, stat, thresh, globalSettings] = await Promise.all([
				fetchCurrent(),
				fetchHistoryRange(startIso, endIso),
				fetchLogsRange(startIso, endIso),
				fetchStatsRange(startIso, endIso),
				fetchThresholds(),
				fetchGlobalSettings()
			]);
			if (cur) {
				if (current?.sgv != null && current.sgv !== cur.sgv) {
					previousSgv = current.sgv;
				} else if (previousSgv === null) {
					previousSgv = cur.sgv;
				}
				current = { sgv: cur.sgv, direction: cur.direction };
				lastUpdate = cur.timestamp;
			}
			readings = hist;
			logs = logEntries;
			stats = stat;
			if (thresh) thresholds = thresh;
			if (globalSettings) insulinActionHours = globalSettings.insulin_action_hours;
		} catch (e) {
			error = 'Dashboard-Daten konnten nicht geladen werden.';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	async function loadPrediction() {
		const [result30, result60, result120] = await Promise.all([
			fetchPrediction(30),
			fetchPrediction(60),
			fetchPrediction(120)
		]);
		// Use 60min result for predictionStatus
		if (!result60) {
			predictionStatus = 'idle';
			predictionPoints60 = [];
		} else {
			predictionStatus = result60.status;
			predictionPoints60 = result60.status === 'ready' ? result60.points : [];
			modelMae60 = result60.status === 'ready' ? ((result60 as any).model_mae ?? null) : null;
			modelVersion = result60.status === 'ready' ? ((result60 as any).model_version ?? '') : '';
		}
		predictionPoints30 = result30?.status === 'ready' ? result30.points : [];
		modelMae30 = result30?.status === 'ready' ? ((result30 as any).model_mae ?? null) : null;
		predictionPoints120 = result120?.status === 'ready' ? result120.points : [];
		modelMae120 = result120?.status === 'ready' ? ((result120 as any).model_mae ?? null) : null;
	}

	function onLogSaved() {
		loadDashboard();
		logRefreshTrigger++;
	}

	async function checkAuth() {
		const res = await fetch('/api/auth/me', {
			headers: { Authorization: `Bearer ${localStorage.getItem('bgmon_token') || ''}` }
		});
		if (!res.ok) {
			goto('/login');
		}
	}

	async function checkHealth() {
		try {
			const res = await fetch('/health');
			if (res.ok) {
				const data = await res.json();
				const libreOk = data.last_libre_fetch_status === 'ok';
				const libreRecent = data.last_libre_fetch_at
					? Date.now() - new Date(data.last_libre_fetch_at).getTime() < 6 * 60 * 1000
					: false;
				health = {
					libre: libreOk && libreRecent
				};
			}
		} catch (e) {
			console.error('Health check failed:', e);
		}
	}

	onMount(() => {
		// Load saved color mode
		const savedColor = localStorage.getItem('bgmon_color_mode');
		if (savedColor === 'dark') {
			document.documentElement.style.colorScheme = 'dark';
		} else if (savedColor === 'light') {
			document.documentElement.style.colorScheme = 'light';
		}
		checkAuth();
		loadDashboard();
		loadPrediction();
		checkHealth();
		checkVersion();
		const interval = setInterval(() => {
			loadDashboard().catch((e) => console.error('Auto-refresh failed:', e));
			loadPrediction().catch((e) => console.error('Prediction refresh failed:', e));
			checkHealth();
		}, 30_000);
		// Check for new app version every 5 minutes
		const versionInterval = setInterval(checkVersion, 5 * 60_000);
		const nowInterval = setInterval(() => {
			now = Date.now();
		}, 1000);
		return () => {
			clearInterval(interval);
			clearInterval(nowInterval);
			clearInterval(versionInterval);
			clearInterval(nowInterval);
		};
	});

	$effect(() => {
		if (current?.sgv != null && previousSgv != null && current.sgv !== previousSgv) {
			pulsing = true;
			setTimeout(() => {
				pulsing = false;
			}, 1500);
		}
	});

	function trendArrow(direction: string | null): string {
		const arrows: Record<string, string> = {
			DoubleDown: '↓↓',
			SingleDown: '↓',
			FortyFiveDown: '↘',
			Flat: '→',
			FortyFiveUp: '↗',
			SingleUp: '↑',
			DoubleUp: '↑↑'
		};
		return arrows[direction ?? ''] ?? '';
	}

	function glucoseColor(sgv: number | null): string {
		if (sgv === null) return 'var(--color-text-muted)';
		if (!health.libre) return 'var(--color-text-muted)';
		if (sgv <= thresholds.critical_low) return '#ef4444';
		if (sgv <= thresholds.low) return '#f97316';
		if (sgv >= thresholds.critical_high) return '#ef4444';
		if (sgv >= thresholds.high) return '#eab308';
		return '#22c55e';
	}

	function timeAgo(timestamp: string | null): string {
		if (!timestamp) return '';
		const then = new Date(timestamp).getTime();
		const diff = Math.max(0, Math.floor((now - then) / 1000));
		if (diff < 60) return `vor ${diff} sec`;
		const mins = Math.floor(diff / 60);
		if (mins < 60) return `vor ${mins} min`;
		const hours = Math.floor(mins / 60);
		return `vor ${hours} h`;
	}

	function formatWindowLabel(): string {
		const sameDay = windowStart.toDateString() === windowEnd.toDateString();
		const timeFmt: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit' };
		if (sameDay) {
			const startStr = windowStart.toLocaleTimeString('de-DE', timeFmt);
			const endStr = windowEnd.toLocaleTimeString('de-DE', timeFmt);
			return `${startStr} – ${endStr}`;
		}
		const fullFmt: Intl.DateTimeFormatOptions = {
			weekday: 'short',
			day: '2-digit',
			month: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		};
		const startStr = windowStart.toLocaleString('de-DE', fullFmt);
		const endStr = windowEnd.toLocaleString('de-DE', fullFmt);
		return `${startStr} – ${endStr}`;
	}
</script>

<div class="sticky-top">
	<header class="app-header">
		<div class="header-pill">
			<div class="header-left">
				<button class="header-logo" type="button">
					<svg
						width="20"
						height="20"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2.5"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						<path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
					</svg>
					<span class="logo-text">bgmon</span>
				</button>

				{#if current}
					<div class="header-sgv-block">
						<button class="sgv-btn" type="button" onclick={() => (bgModalOpen = true)}>
							<span class="sgv {pulsing ? 'pulse' : ''}" style="color: {glucoseColor(current.sgv)}"
								>{current.sgv}</span
							>
							<span class="sgv-label">mg/dL</span>
						</button>
					</div>
				{/if}
			</div>

			<div class="header-actions">
				<LogEntryForm onsaved={onLogSaved} currentBg={current?.sgv ?? null} />
				<ProfileSelector />
			</div>
			<div class="header-right">
				{#if current}
					<div class="header-info-block">
						{#if previousSgv !== null && current.sgv !== null && current.sgv !== previousSgv}
							<span
								class="header-delta"
								style="color: {current.sgv > previousSgv ? '#f97316' : '#22c55e'}"
							>
								{current.sgv > previousSgv ? '+' : ''}{current.sgv - previousSgv}
							</span>
						{/if}
						<span class="sgv-trend" style="color: {glucoseColor(current.sgv)}"
							>{trendArrow(current.direction)}</span
						>
						{#if lastUpdate}
							<span class="header-time">{timeAgo(lastUpdate)}</span>
						{/if}
					</div>
				{/if}
				<SettingsDialog />
			</div>
		</div>
	</header>

	<div class="snooze-bar">
		<SnoozeIndicator />
	</div>
</div>

<BgModal
	bind:open={bgModalOpen}
	sgv={current?.sgv ?? 0}
	direction={current?.direction ?? null}
	color={glucoseColor(current?.sgv ?? null)}
	{lastUpdate}
	{previousSgv}
	predictions30={predictionPoints30}
	predictions60={predictionPoints60}
	predictions120={predictionPoints120}
/>

<div class="dashboard">
	<div class="time-controls">
		<div class="duration-buttons">
			<button class="range-btn now-btn" onclick={jumpToNow} title="Zur aktuellen Zeit springen"
				>Jetzt</button
			>
			{#each durationButtons as btn}
				<button
					class="range-btn"
					class:active={windowDurationMs === btn.ms}
					onclick={() => setDuration(btn.ms)}>{btn.label}</button
				>
			{/each}
		</div>
		<div class="window-label">{formatWindowLabel()}</div>
		<button
			class="refresh-btn"
			onclick={loadDashboard}
			disabled={loading}
			title={loading ? 'Lade...' : 'Aktualisieren'}
		>
			<svg
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2.5"
				stroke-linecap="round"
				stroke-linejoin="round"
				class:spinning={loading}
			>
				<path d="M21 12a9 9 0 1 1-3.36-7"></path>
				<polyline points="21 4 21 10 15 10"></polyline>
			</svg>
		</button>
	</div>

	{#if error}
		<div class="error">{error}</div>
	{/if}

	<div class="content">
		<GlucoseGraph
			{readings}
			{logs}
			criticalLow={thresholds.critical_low}
			low={thresholds.low}
			high={thresholds.high}
			criticalHigh={thresholds.critical_high}
			{insulinActionHours}
			onswipe={shiftWindow}
			{highlightedTimestamp}
			predictions30={predictionPoints30}
			predictions60={predictionPoints60}
			{windowEnd}
		/>
		<LogHistory
			refreshTrigger={logRefreshTrigger}
			{windowStart}
			{windowEnd}
			{highlightedTimestamp}
			onHighlight={(ts: string | null) => (highlightedTimestamp = ts)}
		/>
		<StatsCard
			{stats}
			predictions30={predictionPoints30}
			predictions60={predictionPoints60}
			predictions120={predictionPoints120}
			{modelMae30}
			{modelMae60}
			{modelMae120}
			{modelVersion}
			lastBg={current?.sgv ?? null}
			lastBgTime={lastUpdate ?? undefined}
		/>
	</div>

	{#if newVersionAvailable && !newVersionDismissed}
		<div class="version-banner">
			<span>Neue Version verfügbar — </span>
			<button class="version-reload" onclick={handleVersionReload}>Jetzt neu laden</button>
			<button class="version-dismiss" onclick={() => (newVersionDismissed = true)}>✕</button>
		</div>
	{/if}
	{#if appVersion}
		<div class="version-footer">
			<span>bgmon v{appVersion}</span>
		</div>
	{/if}
</div>

<style>
	.dashboard {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-lg);
		max-width: 900px;
		width: 100%;
		margin: 0 auto;
		padding: 0 var(--spacing-md);
	}

	.sticky-top {
		position: sticky;
		top: 0;
		z-index: 20;
		max-width: 900px;
		margin: 0 auto;
	}

	.app-header {
		padding: calc(env(safe-area-inset-top, 0px) + var(--spacing-md)) var(--spacing-md)
			var(--spacing-sm);
		background: transparent;
	}

	.snooze-bar {
		display: flex;
		justify-content: center;
		padding: 0 var(--spacing-md) var(--spacing-sm);
	}

	.header-pill {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		gap: var(--spacing-md);
		padding: var(--spacing-sm) var(--spacing-md);
		background: var(--color-glass-bg);
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius-pill);
		box-shadow: var(--shadow-lg);
		max-width: 100%;
		min-width: 380px;
		margin: 0 auto;
		overflow: visible;
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: var(--spacing-sm);
		min-width: 0;
		z-index: 1;
	}

	.header-actions {
		display: flex;
		align-items: center;
		gap: var(--spacing-sm);
		overflow: visible;
	}

	.header-right {
		display: flex;
		align-items: center;
		gap: var(--spacing-sm);
		justify-content: flex-end;
	}

	.header-logo {
		display: flex;
		align-items: center;
		gap: var(--spacing-xs);
		padding: var(--spacing-xs) var(--spacing-sm);
		font-weight: 700;
		font-size: 1rem;
		color: var(--color-text);
		background: transparent;
	}

	.header-logo:hover {
		background: var(--color-border-subtle);
	}

	.logo-text {
		display: none;
	}

	@media (min-width: 640px) {
		.logo-text {
			display: inline;
		}
	}

	.header-sgv-block {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 2px;
		line-height: 1.1;
	}

	.sgv-btn {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 2px;
		background: transparent;
		border: none;
		padding: 0;
		margin: 0;
		color: inherit;
		font: inherit;
		cursor: pointer;
		line-height: 1.1;
	}

	.sgv-btn:hover {
		background: rgba(15, 118, 110, 0.08);
	}

	.sgv-btn:hover .sgv {
		text-decoration: underline;
		text-decoration-thickness: 2px;
		text-underline-offset: 4px;
		text-decoration-color: #0f766e;
	}

	.sgv {
		font-size: 2rem;
		font-weight: 800;
		color: var(--color-text);
		line-height: 1;
		display: inline-block;
		transform-origin: center;
		font-variant-numeric: tabular-nums;
	}

	.sgv.pulse {
		animation: pulse-zoom 1.5s ease-out;
	}

	@keyframes pulse-zoom {
		0% {
			transform: scale(1);
			text-shadow: 0 0 0 currentColor;
		}
		30% {
			transform: scale(1.25);
			text-shadow: 0 0 12px currentColor;
		}
		100% {
			transform: scale(1);
			text-shadow: 0 0 0 currentColor;
		}
	}

	.sgv-label {
		color: var(--color-text-muted);
		font-size: 0.7rem;
		font-weight: 500;
	}

	.header-info-block {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
		line-height: 1.1;
	}

	.sgv-trend {
		font-size: 1.1rem;
		font-weight: 700;
		line-height: 1;
	}

	.header-delta {
		font-size: 0.7rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}

	.header-time {
		color: var(--color-text-muted);
		font-size: 0.7rem;
		font-weight: 500;
		white-space: nowrap;
	}

	.time-controls {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: var(--spacing-md);
		background: var(--color-surface);
		padding: var(--spacing-sm) var(--spacing-md);
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius);
		box-shadow: var(--shadow-sm);
	}

	.duration-buttons {
		display: flex;
		gap: var(--spacing-xs);
	}

	.range-btn {
		background: transparent;
		color: var(--color-text-muted);
		padding: var(--spacing-xs) var(--spacing-sm);
		font-size: 0.85rem;
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius);
		min-width: 40px;
	}

	.range-btn:hover:not(.active) {
		background: var(--color-border-subtle);
		color: var(--color-text);
	}

	.range-btn.active {
		color: var(--color-primary);
		border-color: var(--color-primary);
		background: rgba(79, 70, 229, 0.1);
	}

	.window-label {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		font-variant-numeric: tabular-nums;
	}

	.refresh-btn {
		font-size: 0.85rem;
		background: var(--color-primary);
		color: white;
		padding: var(--spacing-xs) var(--spacing-md);
		border: none;
		border-radius: var(--radius);
	}

	.refresh-btn:disabled {
		opacity: 0.5;
	}

	.refresh-btn svg {
		display: block;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.spinning {
		animation: spin 1s linear infinite;
	}

	.error {
		background: #7f1d1d;
		color: #fca5a5;
		padding: var(--spacing-md);
		border-radius: var(--radius);
		text-align: center;
	}

	.content {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-lg);
	}

	.version-banner {
		position: fixed;
		bottom: 32px;
		left: 50%;
		transform: translateX(-50%);
		background: #0f766e;
		color: white;
		padding: 0.6rem 1.2rem;
		border-radius: 999px;
		font-size: 0.85rem;
		font-weight: 600;
		z-index: 900;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		box-shadow: 0 4px 16px rgba(0,0,0,0.2);
	}

	.version-reload {
		background: white;
		color: #0f766e;
		border: none;
		padding: 0.3rem 0.8rem;
		border-radius: 999px;
		font-size: 0.8rem;
		font-weight: 600;
		cursor: pointer;
	}

	.version-dismiss {
		background: none;
		border: none;
		color: white;
		font-size: 1rem;
		cursor: pointer;
		opacity: 0.7;
		padding: 0 0.2rem;
	}

	.version-footer {
		display: flex;
		justify-content: center;
		padding: 0.5rem;
		font-size: 0.7rem;
		color: var(--color-text-muted);
		opacity: 0.5;
	}
</style>
