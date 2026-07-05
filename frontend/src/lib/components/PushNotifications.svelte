<script lang="ts">
	import { apiFetch } from '$lib/auth';
	import { onMount } from 'svelte';

	let subscribed = $state(false);
	let loading = $state(false);
	let error = $state('');
	let publicKey = $state('');

	onMount(() => {
		checkSubscription();
		fetchPublicKey();
	});

	async function fetchPublicKey() {
		const res = await apiFetch('/api/alarms/vapid-public-key');
		if (res.ok) {
			const data = await res.json();
			publicKey = data.public_key;
		}
	}

	async function checkSubscription() {
		if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
			error = 'Push-Benachrichtigungen werden in diesem Browser nicht unterstützt.';
			return;
		}
		const reg = await navigator.serviceWorker.ready;
		const sub = await reg.pushManager.getSubscription();
		subscribed = !!sub;
	}

	async function subscribe() {
		if (!publicKey) {
			error = 'VAPID-Schlüssel nicht verfügbar.';
			return;
		}
		loading = true;
		error = '';
		try {
			const reg = await navigator.serviceWorker.ready;
			const sub = await reg.pushManager.subscribe({
				userVisibleOnly: true,
				applicationServerKey: urlBase64ToUint8Array(publicKey)
			});

			const res = await apiFetch('/api/alarms/subscribe', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					endpoint: sub.endpoint,
					p256dh: arrayBufferToBase64(sub.getKey('p256dh')!),
					auth: arrayBufferToBase64(sub.getKey('auth')!)
				})
			});

			if (res.ok) {
				subscribed = true;
			} else {
				error = 'Fehler beim Speichern der Subscription.';
			}
		} catch (e) {
			error = 'Fehler beim Abonnieren: ' + (e instanceof Error ? e.message : String(e));
		}
		loading = false;
	}

	async function unsubscribe() {
		loading = true;
		error = '';
		try {
			const reg = await navigator.serviceWorker.ready;
			const sub = await reg.pushManager.getSubscription();
			if (sub) {
				await sub.unsubscribe();
				await apiFetch('/api/alarms/unsubscribe', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ endpoint: sub.endpoint })
				});
			}
			subscribed = false;
		} catch (e) {
			error = 'Fehler beim Deabonnieren: ' + (e instanceof Error ? e.message : String(e));
		}
		loading = false;
	}

	function urlBase64ToUint8Array(base64String: string): Uint8Array {
		const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
		const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
		const rawData = window.atob(base64);
		return Uint8Array.from(rawData.split('').map((c) => c.charCodeAt(0)));
	}

	function arrayBufferToBase64(buffer: ArrayBuffer | null): string {
		if (!buffer) return '';
		const bytes = new Uint8Array(buffer);
		let binary = '';
		for (let i = 0; i < bytes.byteLength; i++) {
			binary += String.fromCharCode(bytes[i]);
		}
		return window.btoa(binary);
	}
</script>

<div class="push-panel">
	<h2>Push-Benachrichtigungen</h2>
	{#if error}
		<div class="error">{error}</div>
	{/if}
	{#if subscribed}
		<p class="status">Aktiviert</p>
		<button onclick={unsubscribe} disabled={loading}>
			{loading ? 'Wird deaktiviert...' : 'Deaktivieren'}
		</button>
	{:else}
		<p class="status">Deaktiviert</p>
		<button onclick={subscribe} disabled={loading || !publicKey}>
			{loading ? 'Wird aktiviert...' : 'Aktivieren'}
		</button>
	{/if}
</div>

<style>
	.push-panel {
		background: var(--color-surface);
		padding: var(--spacing-md);
		border-radius: var(--radius);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-sm);
	}

	.push-panel h2 {
		font-size: 1.1rem;
		margin: 0;
		color: var(--color-text);
	}

	.status {
		font-size: 0.9rem;
		color: var(--color-text-muted);
		margin: 0;
	}

	button {
		padding: var(--spacing-xs) var(--spacing-md);
		font-size: 0.9rem;
		background: var(--color-primary);
		color: white;
		border: none;
		border-radius: var(--radius);
		cursor: pointer;
		width: fit-content;
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.error {
		color: #f87171;
		font-size: 0.85rem;
	}
</style>
