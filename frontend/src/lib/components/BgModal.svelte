<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	let {
		open = $bindable(false),
		sgv = 0,
		direction = null as string | null,
		color = '#22c55e',
		lastUpdate = null as string | null,
		previousSgv = null as number | null
	}: {
		open?: boolean;
		sgv?: number;
		direction?: string | null;
		color?: string;
		lastUpdate?: string | null;
		previousSgv?: number | null;
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
		} else {
			releaseWakeLock();
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

	onDestroy(releaseWakeLock);

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
			<div class="bg-value" style="color: {color}">{sgv}</div>
			<div class="bg-unit">mg/dL</div>
			{#if delta !== null}
				<div class="bg-delta" style="color: {deltaColor(delta)}">
					{delta > 0 ? '+' : ''}{delta}
				</div>
			{/if}
			<div class="bg-trend" style="color: {color}">{trendArrow(direction)}</div>
			<div class="bg-time">{timeAgo(lastUpdate)}</div>
		</div>
	</div>
{/if}

<style>
	.bg-modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 100;
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
		z-index: 101;
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
		.bg-modal {
			background: #000;
			color: #f8fafc;
		}
		.close-btn {
			color: #f8fafc;
		}
		.close-btn:hover {
			background: rgba(255, 255, 255, 0.15);
		}
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
</style>
