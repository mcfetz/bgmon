<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { apiFetch } from '$lib/auth';
	import SnoozeModal from './SnoozeModal.svelte';

	type SnoozeState = {
		active: boolean;
		snooze_until: string | null;
		reason: string | null;
	};

	let snooze = $state<SnoozeState>({ active: false, snooze_until: null, reason: null });
	let remaining = $state(0);
	let modalOpen = $state(false);
	let timer: ReturnType<typeof setInterval> | null = null;
	let pollTimer: ReturnType<typeof setInterval> | null = null;

	async function fetchSnooze() {
		try {
			const res = await apiFetch('/api/notifications/snooze');
			if (!res.ok) return;
			snooze = await res.json();
			updateRemaining();
		} catch {}
	}

	function updateRemaining() {
		if (snooze.active && snooze.snooze_until) {
			const end = new Date(snooze.snooze_until).getTime();
			remaining = Math.max(0, Math.floor((end - Date.now()) / 1000));
		} else {
			remaining = 0;
		}
	}

	function formatTime(secs: number): string {
		const m = Math.floor(secs / 60);
		const s = secs % 60;
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	function openModal() {
		modalOpen = true;
	}

	function handleModalUpdate() {
		fetchSnooze();
	}

	onMount(() => {
		fetchSnooze();
		pollTimer = setInterval(fetchSnooze, 30000);
		timer = setInterval(updateRemaining, 1000);
	});

	onDestroy(() => {
		if (pollTimer) clearInterval(pollTimer);
		if (timer) clearInterval(timer);
	});
</script>

{#if snooze.active && remaining > 0}
	<button
		class="snooze-indicator"
		type="button"
		onclick={openModal}
		title={snooze.reason ?? 'Snooze anpassen'}
	>
		<svg
			width="14"
			height="14"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="2.5"
			stroke-linecap="round"
			stroke-linejoin="round"
		>
			<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
		</svg>
		<span class="snooze-text">Stumm</span>
		<span class="snooze-time">{formatTime(remaining)}</span>
	</button>
{/if}

<SnoozeModal bind:open={modalOpen} onUpdate={handleModalUpdate} />

<style>
	.snooze-indicator {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 6px 12px;
		border-radius: 999px;
		background: #f0a000;
		color: #1a1a1a;
		font-size: 0.8rem;
		font-weight: 600;
		white-space: nowrap;
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
		cursor: pointer;
		border: none;
		transition: background 0.15s;
	}

	.snooze-indicator:hover {
		background: #ffb820;
	}

	.snooze-text {
		letter-spacing: 0.02em;
	}

	.snooze-time {
		font-variant-numeric: tabular-nums;
		font-weight: 700;
	}
</style>
