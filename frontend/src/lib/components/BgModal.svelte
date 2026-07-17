<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { apiFetch } from '$lib/auth';
	import SnoozeModal from './SnoozeModal.svelte';

	import type { PredictionPoint } from '$lib/api/dashboard';

	let {
		open = $bindable(false),
		sgv = 0,
		direction = null as string | null,
		color = '#22c55e',
		lastUpdate = null as string | null,
		previousSgv = null as number | null,
		predictions30 = [] as PredictionPoint[],
		predictions60 = [] as PredictionPoint[],
		predictions120 = [] as PredictionPoint[]
	}: {
		open?: boolean;
		sgv?: number;
		direction?: string | null;
		color?: string;
		lastUpdate?: string | null;
		previousSgv?: number | null;
		predictions30?: PredictionPoint[];
		predictions60?: PredictionPoint[];
		predictions120?: PredictionPoint[];
	} = $props();

	const delta = $derived(previousSgv !== null ? sgv - previousSgv : null);

	function deltaColor(d: number | null): string {
		if (d === null || d === 0) return '#94a3b8';
		if (d > 0) return '#f97316';
		return '#22c55e';
	}

	function timeAgo(ts: string | null): string {
		if (!ts) return '—';
		const diff = Date.now() - new Date(ts).getTime();
		const s = Math.floor(diff / 1000);
		if (s < 60) return `vor ${s} Sek.`;
		const m = Math.floor(s / 60);
		if (m < 60) return `vor ${m} Min.`;
		const h = Math.floor(m / 60);
		if (h < 24) return `vor ${h} Std.`;
		const d = Math.floor(h / 24);
		return `vor ${d} Tag${d === 1 ? '' : 'en'}`;
	}

	type SnoozeState = {
		active: boolean;
		snooze_until: string | null;
		reason: string | null;
	};

	let snooze = $state<SnoozeState>({ active: false, snooze_until: null, reason: null });
	let snoozeRemaining = $state(0);
	let snoozeModalOpen = $state(false);
	let snoozeTimer: ReturnType<typeof setInterval> | null = null;
	let snoozePollTimer: ReturnType<typeof setInterval> | null = null;

	async function fetchSnooze() {
		try {
			const res = await apiFetch('/api/notifications/snooze');
			if (!res.ok) return;
			snooze = await res.json();
			updateSnoozeRemaining();
		} catch {}
	}

	function updateSnoozeRemaining() {
		if (snooze.active && snooze.snooze_until) {
			const end = new Date(snooze.snooze_until).getTime();
			snoozeRemaining = Math.max(0, Math.floor((end - Date.now()) / 1000));
		} else {
			snoozeRemaining = 0;
		}
	}

	function formatSnoozeTime(secs: number): string {
		const m = Math.floor(secs / 60);
		const s = secs % 60;
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	function handleSnoozeModalUpdate() {
		fetchSnooze();
	}

	let wakeLock: WakeLockSentinel | null = null;

	function trendArrow(dir: string | null): string {
		const map: Record<string, string> = {
			DoubleUp: '⇈',
			SingleUp: '↑',
			FortyFiveUp: '↗',
			Flat: '→',
			FortyFiveDown: '↘',
			SingleDown: '↓',
			DoubleDown: '⇊'
		};
		return map[dir ?? ''] ?? '→';
	}

	async function requestWakeLock() {
		try {
			if ('wakeLock' in navigator) {
				wakeLock = await navigator.wakeLock.request('screen');
				wakeLock.addEventListener('release', () => {
					wakeLock = null;
				});
			}
		} catch {}
	}

	function releaseWakeLock() {
		wakeLock?.release().catch(() => {});
		wakeLock = null;
	}

	$effect(() => {
		if (open) {
			requestWakeLock();
			fetchSnooze();
			snoozePollTimer = setInterval(fetchSnooze, 30000);
			snoozeTimer = setInterval(updateSnoozeRemaining, 1000);
		} else {
			releaseWakeLock();
			if (snoozePollTimer) {
				clearInterval(snoozePollTimer);
				snoozePollTimer = null;
			}
			if (snoozeTimer) {
				clearInterval(snoozeTimer);
				snoozeTimer = null;
			}
		}
	});

	$effect(() => {
		const handler = () => {
			if (document.visibilityState === 'visible' && open && !wakeLock) {
				requestWakeLock();
			}
		};
		document.addEventListener('visibilitychange', handler);
		return () => document.removeEventListener('visibilitychange', handler);
	});

	onDestroy(() => {
		releaseWakeLock();
		if (snoozePollTimer) clearInterval(snoozePollTimer);
		if (snoozeTimer) clearInterval(snoozeTimer);
	});

	function close() {
		open = false;
	}
</script>

{#if open}
	<button class="bg-modal-backdrop" type="button" onclick={close} aria-label="Schließen"></button>
	<div class="bg-modal" role="dialog" aria-modal="true" aria-label="Aktueller Blutzuckerwert">
		<header class="bg-header">
			<button class="close-btn" type="button" onclick={close} aria-label="Schließen">×</button>
		</header>
		<div class="bg-content">
			{#if snooze.active && snoozeRemaining > 0}
				<button
					class="snooze-display"
					type="button"
					onclick={() => (snoozeModalOpen = true)}
					title={snooze.reason ?? 'Snooze anpassen'}
				>
					<svg
						width="24"
						height="24"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2.5"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
					</svg>
					<span class="snooze-label">Stumm</span>
					<span class="snooze-timer">{formatSnoozeTime(snoozeRemaining)}</span>
				</button>
			{/if}
			<div class="bg-value" style="color: {color}">{sgv}</div>
			<div class="bg-unit">mg/dL</div>
			{#if delta !== null}
				<div class="bg-delta" style="color: {deltaColor(delta)}">
					{delta > 0 ? '+' : ''}{delta}
				</div>
			{/if}
			<div class="bg-trend" style="color: {color}">{trendArrow(direction)}</div>
			<div class="bg-time">{timeAgo(lastUpdate)}</div>

			{#if predictions30.length > 0 || predictions60.length > 0 || predictions120.length > 0}
				<div class="prediction-row">
					{#if predictions30.length > 0}
						{@const p = predictions30[predictions30.length - 1]}
						<div class="prediction-card">
							<span class="pred-label">+30</span>
							<span class="pred-value">{p.predicted_sgv.toFixed(0)}</span>
						</div>
					{/if}
					{#if predictions60.length > 0}
						{@const p = predictions60[predictions60.length - 1]}
						<div class="prediction-card">
							<span class="pred-label">+60</span>
							<span class="pred-value">{p.predicted_sgv.toFixed(0)}</span>
						</div>
					{/if}
					{#if predictions120.length > 0}
						{@const p = predictions120[predictions120.length - 1]}
						<div class="prediction-card">
							<span class="pred-label">+120</span>
							<span class="pred-value">{p.predicted_sgv.toFixed(0)}</span>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>

	<SnoozeModal bind:open={snoozeModalOpen} onUpdate={handleSnoozeModalUpdate} />
{/if}

<style>
	.bg-modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 201;
		border: none;
		padding: 0;
		margin: 0;
		cursor: pointer;
		appearance: none;
		-webkit-appearance: none;
		color: transparent;
		outline: none;
	}

	.bg-modal-backdrop:hover,
	.bg-modal-backdrop:focus,
	.bg-modal-backdrop:focus-visible,
	.bg-modal-backdrop:active {
		background: rgba(0, 0, 0, 0.5);
		outline: none;
		box-shadow: none;
	}

	.bg-modal {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: 90vw;
		height: 90vh;
		max-width: 90vw;
		max-height: 90vh;
		background: var(--color-surface);
		border-radius: var(--radius-lg, 24px);
		z-index: 202;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: var(--spacing-md);
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
	}

	.bg-header {
		display: flex;
		justify-content: flex-end;
		align-self: stretch;
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		font-size: 2.5rem;
		line-height: 1;
		cursor: pointer;
		width: 40px;
		height: 40px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius);
		padding: 0;
	}

	.close-btn:hover {
		background: rgba(255, 255, 255, 0.1);
		color: var(--color-text);
	}

	@media (prefers-color-scheme: dark) {
		.bg-modal:not([data-theme='light'] *) {
			background: #000;
			color: #f8fafc;
		}
		.close-btn:not([data-theme='light'] *) {
			color: #f8fafc;
		}
		.close-btn:not([data-theme='light'] *):hover {
			background: rgba(255, 255, 255, 0.15);
		}
	}
	[data-theme='dark'] .bg-modal {
		background: #000;
		color: #f8fafc;
	}
	[data-theme='dark'] .close-btn {
		color: #f8fafc;
	}
	[data-theme='dark'] .close-btn:hover {
		background: rgba(255, 255, 255, 0.15);
	}

	.bg-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		flex: 1;
		gap: var(--spacing-md);
	}

	.bg-value {
		font-size: min(40vw, 40vh, 400px);
		font-weight: 800;
		line-height: 0.9;
		font-variant-numeric: tabular-nums;
	}

	.bg-unit {
		font-size: clamp(1.5rem, 4vw, 3rem);
		color: var(--color-text-muted);
		font-weight: 500;
	}

	.bg-trend {
		font-size: min(15vw, 15vh, 150px);
		line-height: 0.9;
		font-weight: 700;
	}

	.bg-delta {
		font-size: clamp(1.5rem, 4vw, 3rem);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.bg-time {
		font-size: clamp(1rem, 3vw, 1.5rem);
		color: var(--color-text-muted);
		font-weight: 500;
		font-variant-numeric: tabular-nums;
	}

	.prediction-row {
		display: flex;
		gap: clamp(0.5rem, 2vw, 1.5rem);
		margin-top: clamp(0.5rem, 2vh, 1.5rem);
	}

	.prediction-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.15rem;
		padding: clamp(0.3rem, 1vw, 0.75rem) clamp(0.6rem, 2vw, 1.25rem);
		border-radius: var(--radius, 12px);
		background: rgba(255, 255, 255, 0.06);
	}

	.pred-label {
		font-size: clamp(0.7rem, 1.5vw, 0.85rem);
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		opacity: 0.7;
	}

	.pred-value {
		font-size: clamp(1.3rem, 4vw, 2rem);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}

	@media (prefers-color-scheme: dark) {
		.prediction-card:not([data-theme='light'] *) {
			background: rgba(255, 255, 255, 0.08);
		}
	}
	[data-theme='dark'] .prediction-card {
		background: rgba(255, 255, 255, 0.08);
	}

	.snooze-display {
		display: inline-flex;
		align-items: center;
		gap: 12px;
		padding: 16px 24px;
		border-radius: 999px;
		background: transparent;
		color: var(--color-text-muted);
		font-size: clamp(1.2rem, 3vw, 2rem);
		font-weight: 600;
		white-space: nowrap;
		cursor: pointer;
		border: none;
		transition:
			color 0.15s,
			transform 0.1s;
	}

	.snooze-display:hover {
		color: var(--color-text);
		transform: scale(1.05);
	}

	.snooze-label {
		letter-spacing: 0.02em;
	}

	.snooze-timer {
		font-variant-numeric: tabular-nums;
		font-weight: 700;
	}
</style>
