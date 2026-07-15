<script lang="ts">
	import { apiFetch } from '$lib/auth';
	import { logout } from '$lib/auth';
	import { applyUserColors, getStoredColors, type UserColors } from '$lib/theme';

	let open = $state(false);
	type View =
		| 'main'
		| 'account'
		| 'thresholds'
		| 'treatment'
		| 'twilio'
		| 'push'
		| 'notifications'
		| 'users'
		| 'ml'
		| 'help'
		| 'preferences';
	let currentView = $state<View>('main');

	const SECTIONS: { id: View; label: string; icon: string }[] = [
		{ id: 'account', label: 'Konto', icon: '👤' },
		{ id: 'treatment', label: 'Behandlung', icon: '💊' },
		{ id: 'thresholds', label: 'Schwellwerte', icon: '📊' },
		{ id: 'notifications', label: 'Benachrichtigungen', icon: '🔕' },
		{ id: 'push', label: 'Push', icon: '🔔' },
		{ id: 'twilio', label: 'Twilio', icon: '📞' },
		{ id: 'users', label: 'Benutzer', icon: '👥' },
		{ id: 'ml', label: 'ML', icon: '🧠' },
		{ id: 'preferences', label: 'Einstellungen', icon: '⚙️' },
		{ id: 'help', label: 'Hilfe', icon: '❓' }
	];

	const SECTION_LABELS: Record<View, string> = {
		main: 'Einstellungen',
		account: 'Konto',
		thresholds: 'Schwellwerte',
		treatment: 'Behandlung',
		twilio: 'Twilio',
		push: 'Push',
		notifications: 'Benachrichtigungen',
		users: 'Benutzer',
		ml: 'ML',
		help: 'Hilfe',
		preferences: 'Einstellungen'
	};

	function navigateTo(view: View) {
		currentView = view;
	}

	function goBack() {
		currentView = 'main';
		message = '';
		error = '';
	}

	let email = $state('');
	let phoneNumber = $state('');
	let twilioFromNumber = $state('');
	let availableNumbers = $state<string[]>([]);
	let currentPassword = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let displayName = $state('');
	let snoozeDefaultMinutes = $state(15);
	let colorMode = $state<'auto' | 'light' | 'dark'>('auto');
	let colorBgLight = $state('');
	let colorPrimaryLight = $state('');
	let colorBgDark = $state('');
	let colorPrimaryDark = $state('');
	let currentUserId = $state<number | null>(null);

	let criticalLow = $state(54);
	let low = $state(70);
	let high = $state(180);
	let criticalHigh = $state(250);

	let insulinActionHours = $state(4);
	let correctionFactor = $state(50);
	let carbFactor = $state(1);

	type NotificationArea = 'push' | 'call';
	type NotificationThreshold = 'critical_low' | 'low' | 'high' | 'critical_high';
	const NOTIFICATION_AREAS: NotificationArea[] = ['push', 'call'];
	const NOTIFICATION_THRESHOLDS: NotificationThreshold[] = [
		'critical_low',
		'low',
		'high',
		'critical_high'
	];
	const NOTIFICATION_AREA_LABELS: Record<NotificationArea, string> = {
		push: 'Push',
		call: 'Anruf'
	};
	const NOTIFICATION_THRESHOLD_LABELS: Record<NotificationThreshold, string> = {
		critical_low: 'Critical Low',
		low: 'Low',
		high: 'High',
		critical_high: 'Critical High'
	};

	interface NotificationAssignment {
		id?: number;
		area: NotificationArea;
		threshold: NotificationThreshold;
	}
	interface NotificationProfile {
		id: number;
		name: string;
		icon: string;
		is_active: boolean;
		start_time: string | null;
		assignments: NotificationAssignment[];
		webhook_token: string | null;
	}

	const PROFILE_ICON_SUGGESTIONS = ['☀️', '🌙', '🏠', '🔇', '📱', '🔊', '🔔'];

	let profiles = $state<NotificationProfile[]>([]);
	let editingProfile = $state<NotificationProfile | null>(null);
	let newProfileName = $state('');

	let loading = $state(false);
	let testingCall = $state(false);
	let message = $state('');
	let error = $state('');

	let libreHistoryLoading = $state(false);
	let libreHistoryMessage = $state('');
	let libreHistoryError = $state('');

	let mlTrainStatus = $state('');
	let mlTrainResult = $state<{
		metrics?: { horizon: number; baseline_mae: number; model_mae: number; n_splits: number }[];
	} | null>(null);
	let mlEvalStatus = $state('');
	let mlEvalResult = $state<{
		summaries?: {
			horizon: number;
			model_version: string;
			mae: number;
			matched_points: number;
			completed_runs: number;
			run_count: number;
		}[];
	} | null>(null);

	let pushSubscribed = $state(false);
	let pushLoading = $state(false);
	let pushError = $state('');
	let pushPublicKey = $state('');
	let pushTesting = $state(false);
	let pushTestMessage = $state('');
	let copyState = $state<string | null>(null);

	interface UserRow {
		id: number;
		email: string;
		display_name: string;
		role: string;
		is_active: boolean;
		created_at: string | null;
	}
	let users = $state<UserRow[]>([]);
	let newUserEmail = $state('');
	let newUserPassword = $state('');
	let newUserIsPatient = $state(false);
	let newUserError = $state('');
	let newUserLoading = $state(false);

	const patientExists = $derived(users.some((u) => u.role === 'patient'));

	async function fetchUsers() {
		const res = await apiFetch('/api/users');
		if (res.ok) {
			users = await res.json();
		}
	}

	async function reloadLibreHistory() {
		libreHistoryLoading = true;
		libreHistoryMessage = '';
		libreHistoryError = '';
		try {
			const res = await apiFetch('/api/settings/libre/reload-history', {
				method: 'POST'
			});
			if (res.ok) {
				const data = await res.json();
				libreHistoryMessage = data.message || 'Historische Daten erfolgreich geladen';
			} else {
				const data = await res.json();
				libreHistoryError = data.error || 'Fehler beim Laden der historischen Daten';
			}
		} catch (e) {
			libreHistoryError = 'Netzwerkfehler: ' + (e instanceof Error ? e.message : String(e));
		} finally {
			libreHistoryLoading = false;
		}
	}

	function pollMlJob(
		endpoint: string,
		jobId: string,
		setStatus: (s: string) => void,
		setResult: (r: Record<string, unknown>) => void
	) {
		const interval = setInterval(async () => {
			try {
				const res = await apiFetch(endpoint.replace('(job_id)', jobId));
				if (!res.ok) {
					clearInterval(interval);
					setStatus('Fehler: ' + res.status);
					return;
				}
				const data = await res.json();
				if (data.status === 'completed') {
					clearInterval(interval);
					setStatus('completed');
					setResult(data);
				} else if (data.status === 'error') {
					clearInterval(interval);
					setStatus('Fehler: ' + (data.error || 'Unbekannter Fehler'));
				} else {
					setStatus('running…');
				}
			} catch (e) {
				clearInterval(interval);
				setStatus('Netzwerkfehler: ' + (e instanceof Error ? e.message : String(e)));
			}
		}, 2000);
	}

	async function startMlTrain() {
		mlTrainStatus = 'starte…';
		mlTrainResult = null;
		try {
			const res = await apiFetch('/api/settings/ml/train', { method: 'POST' });
			if (!res.ok) {
				const data = await res.json();
				mlTrainStatus = 'Fehler: ' + (data.error || res.status);
				return;
			}
			const data = await res.json();
			mlTrainStatus = 'running…';
			pollMlJob(
				'/api/settings/ml/train/(job_id)',
				data.job_id,
				(s) => (mlTrainStatus = s),
				(r) => (mlTrainResult = r)
			);
		} catch (e) {
			mlTrainStatus = 'Netzwerkfehler: ' + (e instanceof Error ? e.message : String(e));
		}
	}

	async function startMlEvaluate() {
		mlEvalStatus = 'starte…';
		mlEvalResult = null;
		try {
			const res = await apiFetch('/api/settings/ml/evaluate', { method: 'POST' });
			if (!res.ok) {
				const data = await res.json();
				mlEvalStatus = 'Fehler: ' + (data.error || res.status);
				return;
			}
			const data = await res.json();
			mlEvalStatus = 'running…';
			pollMlJob(
				'/api/settings/ml/evaluate/(job_id)',
				data.job_id,
				(s) => (mlEvalStatus = s),
				(r) => (mlEvalResult = r)
			);
		} catch (e) {
			mlEvalStatus = 'Netzwerkfehler: ' + (e instanceof Error ? e.message : String(e));
		}
	}

	async function createUser() {
		newUserError = '';
		if (!newUserEmail.trim()) {
			newUserError = 'Email erforderlich.';
			return;
		}
		if (!newUserPassword || newUserPassword.length < 6) {
			newUserError = 'Passwort muss mindestens 6 Zeichen haben.';
			return;
		}
		if (newUserIsPatient && patientExists) {
			newUserError = 'Es existiert bereits ein Patient.';
			return;
		}
		newUserLoading = true;
		try {
			const res = await apiFetch('/api/users', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					email: newUserEmail.trim(),
					password: newUserPassword,
					role: newUserIsPatient ? 'patient' : 'observer',
					display_name: newUserEmail.trim().split('@')[0]
				})
			});
			if (res.ok) {
				newUserEmail = '';
				newUserPassword = '';
				newUserIsPatient = false;
				await fetchUsers();
			} else {
				const data = await res.json().catch(() => ({}));
				newUserError = data.error || 'Fehler beim Anlegen.';
			}
		} catch (e) {
			newUserError = 'Fehler: ' + (e instanceof Error ? e.message : String(e));
		}
		newUserLoading = false;
	}

	function webhookUrl(token: string): string {
		return `${window.location.origin}/api/notifications/webhook/${token}`;
	}

	async function copyWebhook(token: string) {
		try {
			await navigator.clipboard.writeText(webhookUrl(token));
		} catch {}
		copyState = token;
		setTimeout(() => {
			if (copyState === token) copyState = null;
		}, 1500);
	}

	async function checkPushSubscription() {
		if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
			return;
		}
		const reg = await navigator.serviceWorker.ready;
		const sub = await reg.pushManager.getSubscription();
		pushSubscribed = !!sub;
	}

	async function fetchPushPublicKey() {
		const res = await apiFetch('/api/alarms/vapid-public-key');
		if (res.ok) {
			const data = await res.json();
			pushPublicKey = data.public_key;
		}
	}

	async function subscribePush() {
		if (!pushPublicKey) {
			pushError = 'VAPID-Schlüssel nicht verfügbar.';
			return;
		}
		pushLoading = true;
		pushError = '';
		try {
			const reg = await navigator.serviceWorker.ready;
			const key = urlBase64ToUint8Array(pushPublicKey);
			const sub = await reg.pushManager.subscribe({
				userVisibleOnly: true,
				applicationServerKey: key
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
				pushSubscribed = true;
			} else {
				pushError = 'Fehler beim Speichern der Subscription.';
			}
		} catch (e) {
			pushError = 'Fehler beim Abonnieren: ' + (e instanceof Error ? e.message : String(e));
		}
		pushLoading = false;
	}

	async function unsubscribePush() {
		pushLoading = true;
		pushError = '';
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
			pushSubscribed = false;
		} catch (e) {
			pushError = 'Fehler beim Deabonnieren: ' + (e instanceof Error ? e.message : String(e));
		}
		pushLoading = false;
	}

	async function sendTestPush() {
		pushTesting = true;
		pushTestMessage = '';
		try {
			const res = await apiFetch('/api/alarms/test-push', { method: 'POST' });
			if (res.ok) {
				pushTestMessage = 'Test-Push gesendet. Prüfe deine Notifications.';
			} else {
				pushTestMessage = 'Fehler beim Senden.';
			}
		} catch (e) {
			pushTestMessage = 'Fehler: ' + (e instanceof Error ? e.message : String(e));
		}
		pushTesting = false;
	}

	function urlBase64ToUint8Array(base64String: string): ArrayBuffer {
		const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
		const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
		const rawData = window.atob(base64);
		const arr = new Uint8Array(rawData.length);
		for (let i = 0; i < rawData.length; i++) {
			arr[i] = rawData.charCodeAt(i);
		}
		return arr.buffer;
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

	async function openModal() {
		open = true;
		currentView = 'main';
		message = '';
		error = '';
		currentPassword = '';
		newPassword = '';
		confirmPassword = '';
		newProfileName = '';
		editingProfile = null;
		pushError = '';
		pushTestMessage = '';
		// Load preferences from localStorage (instant)
		snoozeDefaultMinutes = parseInt(localStorage.getItem('bgmon_snooze_default') || '15');
		colorMode = (localStorage.getItem('bgmon_color_mode') || 'auto') as 'auto' | 'light' | 'dark';
		colorBgLight = localStorage.getItem('bgmon_color_bg_light') || '';
		colorPrimaryLight = localStorage.getItem('bgmon_color_primary_light') || '';
		colorBgDark = localStorage.getItem('bgmon_color_bg_dark') || '';
		colorPrimaryDark = localStorage.getItem('bgmon_color_primary_dark') || '';
		await loadData();
		await loadProfiles();
		await fetchPushPublicKey();
		await checkPushSubscription();
		await fetchUsers();
	}

	async function loadData() {
		loading = true;
		try {
			const [globalRes, thresholdsRes, carbRes, meRes, twilioRes] = await Promise.all([
				apiFetch('/api/settings/global'),
				apiFetch('/api/settings/thresholds'),
				apiFetch('/api/log/carb-factor'),
				apiFetch('/api/auth/me'),
				apiFetch('/api/settings/twilio/numbers')
			]);

			if (globalRes.ok) {
				const data = await globalRes.json();
				insulinActionHours = data.insulin_action_hours ?? 4;
				correctionFactor = data.correction_factor ?? 50;
			}

			if (thresholdsRes.ok) {
				const data = await thresholdsRes.json();
				criticalLow = data.critical_low ?? 54;
				low = data.low ?? 70;
				high = data.high ?? 180;
				criticalHigh = data.critical_high ?? 250;
			}

			if (carbRes.ok) {
				const data = await carbRes.json();
				carbFactor = data.current?.factor ?? 1;
			}

			if (meRes.ok) {
				const data = await meRes.json();
				email = data.email ?? '';
				phoneNumber = data.phone_number ?? '';
				displayName = data.display_name ?? '';
				currentUserId = data.id ?? null;
			}

			if (twilioRes.ok) {
				const data = await twilioRes.json();
				availableNumbers = data.numbers ?? [];
				twilioFromNumber = data.current ?? '';
			}
		} catch (e) {
			console.error('Failed to load settings:', e);
		} finally {
			loading = false;
		}
	}

	async function savePreferences() {
		error = '';
		message = '';
		localStorage.setItem('bgmon_snooze_default', String(snoozeDefaultMinutes));
		localStorage.setItem('bgmon_color_mode', colorMode);
		localStorage.setItem('bgmon_color_bg_light', colorBgLight);
		localStorage.setItem('bgmon_color_primary_light', colorPrimaryLight);
		localStorage.setItem('bgmon_color_bg_dark', colorBgDark);
		localStorage.setItem('bgmon_color_primary_dark', colorPrimaryDark);
		applyColorMode(colorMode);
		try {
			await apiFetch('/api/settings/preferences', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					snooze_default_minutes: snoozeDefaultMinutes,
					color_mode: colorMode,
					color_bg_light: colorBgLight || null,
					color_primary_light: colorPrimaryLight || null,
					color_bg_dark: colorBgDark || null,
					color_primary_dark: colorPrimaryDark || null
				})
			});
		} catch {}
		message = 'Gespeichert';
	}

	function applyColorMode(mode: string) {
		const root = document.documentElement;
		if (mode === 'dark') {
			root.setAttribute('data-theme', 'dark');
		} else if (mode === 'light') {
			root.setAttribute('data-theme', 'light');
		} else {
			root.removeAttribute('data-theme');
		}
		applyUserColors({
			bgLight: colorBgLight, primaryLight: colorPrimaryLight,
			bgDark: colorBgDark, primaryDark: colorPrimaryDark,
			mode
		});
	}

	async function saveAccount() {
		error = '';
		message = '';

		if (currentUserId !== null && displayName.trim()) {
			const res = await apiFetch(`/api/users/${currentUserId}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ display_name: displayName.trim() })
			});
			if (!res.ok) {
				const data = await res.json();
				error = data.error || 'Name konnte nicht gespeichert werden';
				return;
			}
		}

		if (email) {
			const res = await apiFetch('/api/settings/email', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email })
			});
			if (!res.ok) {
				const data = await res.json();
				error = data.error || 'Email konnte nicht gespeichert werden';
				return;
			}
		}

		if (newPassword) {
			if (newPassword !== confirmPassword) {
				error = 'Passwörter stimmen nicht überein';
				return;
			}
			if (!currentPassword) {
				error = 'Aktuelles Passwort erforderlich';
				return;
			}
			const res = await apiFetch('/api/settings/password', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
			});
			if (!res.ok) {
				const data = await res.json();
				error = data.error || 'Passwort konnte nicht geändert werden';
				return;
			}
			currentPassword = '';
			newPassword = '';
			confirmPassword = '';
		}

		message = 'Konto-Einstellungen gespeichert';
	}

	async function saveThresholds() {
		error = '';
		message = '';

		const res = await apiFetch('/api/settings/thresholds', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				critical_low: criticalLow,
				low,
				high,
				critical_high: criticalHigh
			})
		});

		if (!res.ok) {
			const data = await res.json();
			error = data.error || 'Schwellwerte konnten nicht gespeichert werden';
			return;
		}

		message = 'Schwellwerte gespeichert';
	}

	async function saveTreatment() {
		error = '';
		message = '';

		const [globalRes, carbRes] = await Promise.all([
			apiFetch('/api/settings/global', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					insulin_action_hours: insulinActionHours,
					correction_factor: correctionFactor
				})
			}),
			apiFetch('/api/log/carb-factor', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ factor: carbFactor })
			})
		]);

		if (!globalRes.ok || !carbRes.ok) {
			error = 'Behandlungs-Einstellungen konnten nicht gespeichert werden';
			return;
		}

		message = 'Behandlungs-Einstellungen gespeichert';
	}

	async function saveTwilio() {
		error = '';
		message = '';

		if (twilioFromNumber && twilioFromNumber === phoneNumber.trim()) {
			error = 'Anrufende und angerufene Nummer dürfen nicht identisch sein';
			return;
		}

		const res = await apiFetch('/api/settings/twilio', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				from_number: twilioFromNumber,
				phone_number: phoneNumber
			})
		});

		if (!res.ok) {
			const data = await res.json();
			error = data.error || 'Twilio-Einstellungen konnten nicht gespeichert werden';
			return;
		}

		const data = await res.json();
		if (data.phone_number !== undefined) {
			phoneNumber = data.phone_number;
		}
		message = 'Twilio-Einstellungen gespeichert';
	}

	async function loadProfiles() {
		const res = await apiFetch('/api/notifications/profiles');
		if (res.ok) {
			profiles = await res.json();
		}
	}

	async function createProfile() {
		error = '';
		message = '';
		if (!newProfileName.trim()) {
			error = 'Bitte einen Namen eingeben';
			return;
		}
		const res = await apiFetch('/api/notifications/profiles', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: newProfileName.trim(), icon: '🔔', assignments: [] })
		});
		if (!res.ok) {
			const data = await res.json();
			error = data.error || 'Profil konnte nicht erstellt werden';
			return;
		}
		const created: NotificationProfile = await res.json();
		profiles = [...profiles, created];
		newProfileName = '';
		message = `Profil "${created.name}" erstellt`;
	}

	async function saveProfile() {
		if (!editingProfile) return;
		error = '';
		message = '';

		const res = await apiFetch(`/api/notifications/profiles/${editingProfile.id}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				name: editingProfile.name,
				icon: editingProfile.icon,
				start_time: editingProfile.start_time || null,
				assignments: editingProfile.assignments
			})
		});

		if (!res.ok) {
			const data = await res.json();
			error = data.error || 'Profil konnte nicht gespeichert werden';
			return;
		}

		const updated: NotificationProfile = await res.json();
		profiles = profiles.map((p) => (p.id === updated.id ? updated : p));
		editingProfile = { ...updated };
		message = `Profil "${updated.name}" gespeichert`;
	}

	async function deleteProfile(id: number) {
		if (!confirm('Profil wirklich löschen?')) return;
		const res = await apiFetch(`/api/notifications/profiles/${id}`, { method: 'DELETE' });
		if (res.ok) {
			profiles = profiles.filter((p) => p.id !== id);
			if (editingProfile?.id === id) editingProfile = null;
			message = 'Profil gelöscht';
		}
	}

	function setAssignment(threshold: NotificationThreshold, area: NotificationArea | '') {
		if (!editingProfile) return;
		editingProfile.assignments = editingProfile.assignments.filter(
			(a) => a.threshold !== threshold
		);
		if (area) {
			editingProfile.assignments = [...editingProfile.assignments, { area, threshold }];
		}
	}

	function getAssignedArea(threshold: NotificationThreshold): NotificationArea | '' {
		if (!editingProfile) return '';
		return editingProfile.assignments.find((a) => a.threshold === threshold)?.area ?? '';
	}

	async function testCall() {
		error = '';
		message = '';

		if (!phoneNumber.trim()) {
			error = 'Bitte zuerst eine Telefonnummer eingeben';
			return;
		}

		testingCall = true;
		try {
			const res = await apiFetch('/api/settings/twilio/test', {
				method: 'POST'
			});
			if (!res.ok) {
				const data = await res.json();
				error = data.error || 'Testanruf fehlgeschlagen';
				return;
			}
			const data = await res.json();
			message = `Testanruf gestartet: ${data.from} → ${data.to}`;
		} catch (e) {
			error = 'Testanruf fehlgeschlagen: ' + (e instanceof Error ? e.message : String(e));
		} finally {
			testingCall = false;
		}
	}

	function switchTab(tab: View) {
		navigateTo(tab);
		message = '';
		error = '';
	}
</script>

<button class="settings-btn" onclick={openModal} title="Einstellungen">
	<svg
		width="20"
		height="20"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="2"
	>
		<circle cx="12" cy="12" r="3"></circle>
		<path
			d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
		></path>
	</svg>
</button>

{#if open}
	<div
		class="modal-backdrop"
		onclick={(e) => {
			if (e.target === e.currentTarget) open = false;
		}}
	>
		<div class="modal">
			<div class="modal-header">
				{#if currentView !== 'main'}
					<button class="back-btn" type="button" onclick={goBack} aria-label="Zurück">‹</button>
				{/if}
				<h2>{SECTION_LABELS[currentView]}</h2>
				<button
					class="close-btn"
					type="button"
					onclick={() => (open = false)}
					aria-label="Schließen">×</button
				>
			</div>

			<div class="modal-body">
				{#if loading}
					<p class="loading">Lade...</p>
				{:else if currentView === 'main'}
					<nav class="section-list">
						{#each SECTIONS as section}
							<button class="section-item" type="button" onclick={() => navigateTo(section.id)}>
								<span class="section-icon">{section.icon}</span>
								<span class="section-name">{section.label}</span>
								<span class="section-chevron">›</span>
							</button>
						{/each}
					</nav>
				{:else if currentView === 'account'}
					<div class="field">
						<label>Name</label>
						<input type="text" bind:value={displayName} placeholder="Anzeigename" />
					</div>

					<div class="field">
						<label>Email</label>
						<input type="email" bind:value={email} placeholder="email@example.com" />
					</div>

					<div class="field">
						<label>Aktuelles Passwort</label>
						<input
							type="password"
							bind:value={currentPassword}
							placeholder="Für Passwort-Änderung"
						/>
					</div>

					<div class="field">
						<label>Neues Passwort</label>
						<input type="password" bind:value={newPassword} placeholder="Mindestens 6 Zeichen" />
					</div>

					<div class="field">
						<label>Passwort bestätigen</label>
						<input
							type="password"
							bind:value={confirmPassword}
							placeholder="Neues Passwort wiederholen"
						/>
					</div>

					<button class="submit-btn" onclick={saveAccount}>Speichern</button>

					<button class="logout-btn" onclick={logout}>Abmelden</button>
				{:else if currentView === 'thresholds'}
					<div class="field">
						<label>Kritisch niedrig (mg/dL)</label>
						<input type="number" bind:value={criticalLow} min="30" max="100" />
					</div>

					<div class="field">
						<label>Niedrig (mg/dL)</label>
						<input type="number" bind:value={low} min="50" max="120" />
					</div>

					<div class="field">
						<label>Hoch (mg/dL)</label>
						<input type="number" bind:value={high} min="140" max="250" />
					</div>

					<div class="field">
						<label>Kritisch hoch (mg/dL)</label>
						<input type="number" bind:value={criticalHigh} min="180" max="350" />
					</div>

					<button class="submit-btn" onclick={saveThresholds}>Speichern</button>
				{:else if currentView === 'treatment'}
					<div class="field">
						<label>KE-Faktor (IE pro g KE)</label>
						<input
							type="number"
							inputmode="decimal"
							bind:value={carbFactor}
							min="0.1"
							max="10"
							step="0.1"
						/>
						<p class="hint">
							Wie viel Insulin pro Gramm Kohlenhydrate. Beispiel: 1.3 → 10g KE brauchen 13 U
							Insulin.
						</p>
					</div>

					<div class="field">
						<label>Insulin-Wirkzeit (Stunden)</label>
						<input type="number" bind:value={insulinActionHours} min="1" max="8" step="0.5" />
					</div>

					<div class="field">
						<label>Korrekturfaktor (mg/dL pro IE Insulin)</label>
						<input
							type="number"
							inputmode="decimal"
							bind:value={correctionFactor}
							min="1"
							max="200"
							step="1"
						/>
						<p class="hint">
							Wie viele mg/dL eine Einheit Insulin senkt. Beispiel: 50 → 1 IE senkt BG um 50 Punkte.
						</p>
					</div>

					<button class="submit-btn" onclick={saveTreatment}>Speichern</button>

					<div class="field">
						<label>LibreLinkUp Historische Daten</label>
						<p class="hint">
							Lade die letzten 12 Stunden historische Daten von LibreLinkUp um Lücken im Graph zu
							füllen.
						</p>
						<button class="submit-btn" onclick={reloadLibreHistory} disabled={libreHistoryLoading}>
							{libreHistoryLoading ? 'Lade...' : 'Historische Daten laden'}
						</button>
						{#if libreHistoryMessage}
							<p class="success">{libreHistoryMessage}</p>
						{/if}
						{#if libreHistoryError}
							<p class="error">{libreHistoryError}</p>
						{/if}
					</div>
				{:else if currentView === 'twilio'}
					<div class="field">
						<label>Telefonnummer (für eingehende Anrufe)</label>
						<input type="tel" bind:value={phoneNumber} placeholder="+491234567890" />
					</div>

					<div class="field">
						<label>Anrufende Nummer (Twilio From)</label>
						{#if availableNumbers.length > 0}
							<select bind:value={twilioFromNumber}>
								<option value="">— Standard (Server) —</option>
								{#each availableNumbers as num}
									<option value={num}>{num}</option>
								{/each}
							</select>
						{:else}
							<p class="hint">
								Keine Twilio-Nummern konfiguriert. Setze BGMON_TWILIO_NUMBERS in der .env Datei.
							</p>
						{/if}
					</div>

					{#if twilioFromNumber && twilioFromNumber === phoneNumber.trim()}
						<p class="error">Anrufende und angerufene Nummer müssen unterschiedlich sein.</p>
					{/if}

					<div class="button-row">
						<button class="submit-btn" onclick={saveTwilio}>Speichern</button>
						<button class="test-btn" onclick={testCall} disabled={testingCall}>
							{testingCall ? 'Wählt...' : 'Testanruf'}
						</button>
					</div>
				{:else if currentView === 'push'}
					{#if !('serviceWorker' in navigator) || !('PushManager' in window)}
						<p class="error">Push-Benachrichtigungen werden in diesem Browser nicht unterstützt.</p>
					{:else}
						<p class="hint">
							{pushSubscribed
								? 'Push ist in diesem Browser aktiviert. Du erhältst Benachrichtigungen wenn BG-Schwellwerte überschritten werden.'
								: 'Aktiviere Push um auch bei geschlossenem Tab alarmiert zu werden.'}
						</p>

						{#if pushError}
							<p class="error">{pushError}</p>
						{/if}

						<div class="field-row">
							{#if pushSubscribed}
								<button class="submit-btn" onclick={unsubscribePush} disabled={pushLoading}>
									{pushLoading ? 'Wird deaktiviert...' : 'Push deaktivieren'}
								</button>
							{:else}
								<button
									class="submit-btn"
									onclick={subscribePush}
									disabled={pushLoading || !pushPublicKey}
								>
									{pushLoading ? 'Wird aktiviert...' : 'Push aktivieren'}
								</button>
							{/if}
							<button
								class="test-btn"
								onclick={sendTestPush}
								disabled={pushTesting || !pushSubscribed}
							>
								{pushTesting ? 'Sende...' : 'Test-Push senden'}
							</button>
						</div>

						{#if pushTestMessage}
							<p class="hint">{pushTestMessage}</p>
						{/if}
					{/if}
				{:else if currentView === 'notifications'}
					<div class="field-row">
						<input type="text" bind:value={newProfileName} placeholder="Neuer Profil-Name" />
						<button class="test-btn" onclick={createProfile}>+ Profil</button>
					</div>

					<div class="profile-list">
						{#each profiles as profile (profile.id)}
							<div class="profile-item" class:editing={editingProfile?.id === profile.id}>
								<button
									class="profile-header"
									type="button"
									onclick={() =>
										(editingProfile = editingProfile?.id === profile.id ? null : profile)}
								>
									<span class="profile-name">{profile.name}</span>
									<span class="profile-count">{profile.assignments.length}/4</span>
								</button>
								{#if editingProfile?.id === profile.id}
									<div class="profile-editor">
										<div class="row-fields">
											<div class="field grow">
												<label>Name</label>
												<input type="text" bind:value={editingProfile.name} />
											</div>
											<div class="field">
												<label>Startzeit</label>
												<input
													type="time"
													inputmode="numeric"
													bind:value={editingProfile.start_time}
													class="time-input"
												/>
											</div>
										</div>
										<div class="field">
											<label>Icon</label>
											<div class="icon-row">
												<input
													type="text"
													bind:value={editingProfile.icon}
													maxlength="4"
													placeholder="🔔"
													class="icon-input"
												/>
												<div class="icon-suggestions">
													{#each PROFILE_ICON_SUGGESTIONS as emoji}
														<button
															type="button"
															class="icon-suggestion"
															onclick={() => editingProfile && (editingProfile.icon = emoji)}
															>{emoji}</button
														>
													{/each}
												</div>
											</div>
										</div>
										{#each NOTIFICATION_THRESHOLDS as threshold}
											<div class="field">
												<label>{NOTIFICATION_THRESHOLD_LABELS[threshold]}</label>
												<select
													value={getAssignedArea(threshold)}
													onchange={(e) =>
														setAssignment(
															threshold,
															(e.currentTarget as HTMLSelectElement).value as NotificationArea | ''
														)}
												>
													<option value="">— Nicht aktiv —</option>
													{#each NOTIFICATION_AREAS as area}
														<option value={area}>{NOTIFICATION_AREA_LABELS[area]}</option>
													{/each}
												</select>
											</div>
										{/each}
										{#if profile.webhook_token}
										<div class="field">
											<label>Webhook (aktiviert dieses Profil)</label>
											<div class="webhook-row">
												<input
													type="text"
													readonly
													value={webhookUrl(profile.webhook_token)}
													class="webhook-input"
												/>
												<button
													type="button"
													class="test-btn"
													onclick={() => { if (profile.webhook_token) copyWebhook(profile.webhook_token); }}
													>{copyState === profile.webhook_token ? '✓' : 'Kopieren'}</button
												>
											</div>
										</div>
									{/if}
										<div class="button-row">
											<button class="submit-btn" onclick={saveProfile}>Speichern</button>
											<button class="test-btn" onclick={() => deleteProfile(profile.id)}
												>Löschen</button
											>
										</div>
									</div>
								{/if}
							</div>
						{:else}
							<p class="hint">Noch keine Profile. Erstelle eines oben.</p>
						{/each}
					</div>
				{:else if currentView === 'help'}
					<div class="help-content">
						<h3>Was ist bgmon?</h3>
						<p>
							bgmon zeigt den aktuellen Blutzucker live an — alle 60 Sekunden von LibreLinkUp.
							Du kannst KE und Insulin eintragen, wirst bei gefährlichen Werten alarmiert und
							bekommst eine Vorhersage für 30/60/120 Minuten.
						</p>

						<h3>Dashboard</h3>
						<ul>
							<li><strong>BG-Wert</strong> — Grün (70–180), Gelb, Rot. Trendpfeil + Delta</li>
							<li><strong>Zeitangabe</strong> unter dem Wert: „vor X Min." — über 10 Min. = Sensor prüfen</li>
							<li><strong>Graph</strong> — Zoom-Buttons (-1h … -1w), Jetzt, Wischgeste, Punkt antippen</li>
							<li><strong>Großer BG-Bildschirm</strong> — Auf den Wert tippen, bleibt mit Wake Lock an</li>
						</ul>

						<h3>Eintragungen</h3>
						<ul>
							<li><strong>KE</strong> — 1 KE = 10 g, nur ganze Zahlen</li>
							<li><strong>Insulin</strong> — 0,5er-Schritte, automatischer Vorschlag aus KE×Faktor+Korrektur</li>
							<li><strong>Basal</strong> — Einmal täglich, letzter Wert als Vorschlag</li>
							<li><strong>Notiz</strong> — Freitext</li>
							<li><strong>Simulation</strong> — Gestrichelte Linie im Graph beim Eintippen (vor dem Speichern)</li>
							<li><strong>Löschen</strong> — Log-Einträge mit 🗑️-Button entfernen</li>
						</ul>

						<h3>Alarme & Push</h3>
						<ul>
							<li>Schwellwerte: &lt;54 kritisch, &lt;70 niedrig, &gt;180 hoch, &gt;250 kritisch (anpassbar)</li>
							<li>Push: Nur mit installierter App (Homescreen). Bei Erstabfrage „Erlauben" wählen</li>
							<li>Telefonanruf (Twilio): Automatischer Anruf mit Sprachansage</li>
							<li>15-Min-Snooze nach jedem Alarm</li>
							<li>Notification-Profile: Profile für Tag/Nacht, je Schwellwert Push/Anruf wählbar</li>
						</ul>

						<h3>Familie-Dashboard</h3>
						<ul>
							<li>Öffentlicher Link für Oma/Opa/Betreuer ohne Login</li>
							<li>Token aus Notification-Profil: <code>/api/family/&lt;token&gt;</code></li>
						</ul>

						<h3>Prognose (ML)</h3>
						<ul>
							<li>30/60/120 Min. Vorhersage im Graph (gestrichelt), Kachel und BG-Modal</li>
							<li>MAE = Genauigkeit (wird besser mit mehr Daten)</li>
						</ul>

						<h3>Einstellungen</h3>
						<ul>
							<li><strong>Behandlung</strong>: KE-Faktor, Korrekturfaktor, Insulinwirkzeit</li>
							<li><strong>Schwellwerte</strong>: Alarmgrenzen pro Benutzer</li>
							<li><strong>Benachrichtigungen</strong>: Profile, Push/Anruf, Nachtzeiten, Webhook</li>
							<li><strong>Twilio</strong>: Telefonnummern, Testanruf</li>
							<li><strong>Benutzer</strong>: Anlegen/Verwalten (Admin)</li>
							<li><strong>ML</strong>: Modell trainieren + evaluieren</li>
						</ul>
					</div>
				{:else if currentView === 'preferences'}
					<div class="field">
						<label>Standard-Snooze (Minuten)</label>
						<input type="number" bind:value={snoozeDefaultMinutes} min="1" max="120" />
					</div>
					<div class="field">
						<label>Farbmodus</label>
						<select bind:value={colorMode}>
							<option value="auto">Auto (System)</option>
							<option value="light">Hell</option>
							<option value="dark">Dunkel</option>
						</select>
					</div>
					<h3 class="sub-heading">Farben Hell</h3>
					<div class="field">
						<label>Hintergrund</label>
						<div class="color-row">
							<input type="color" bind:value={colorBgLight} />
							<input type="text" bind:value={colorBgLight} placeholder="#f8fafc" maxlength="7" />
							<button type="button" class="test-btn" onclick={() => (colorBgLight = '')}>Reset</button>
						</div>
					</div>
					<div class="field">
						<label>Akzentfarbe</label>
						<div class="color-row">
							<input type="color" bind:value={colorPrimaryLight} />
							<input type="text" bind:value={colorPrimaryLight} placeholder="#4f46e5" maxlength="7" />
							<button type="button" class="test-btn" onclick={() => (colorPrimaryLight = '')}>Reset</button>
						</div>
					</div>
					<h3 class="sub-heading">Farben Dunkel</h3>
					<div class="field">
						<label>Hintergrund</label>
						<div class="color-row">
							<input type="color" bind:value={colorBgDark} />
							<input type="text" bind:value={colorBgDark} placeholder="#020617" maxlength="7" />
							<button type="button" class="test-btn" onclick={() => (colorBgDark = '')}>Reset</button>
						</div>
					</div>
					<div class="field">
						<label>Akzentfarbe</label>
						<div class="color-row">
							<input type="color" bind:value={colorPrimaryDark} />
							<input type="text" bind:value={colorPrimaryDark} placeholder="#4f46e5" maxlength="7" />
							<button type="button" class="test-btn" onclick={() => (colorPrimaryDark = '')}>Reset</button>
						</div>
					</div>
					<button class="submit-btn" onclick={savePreferences}>Speichern</button>
				{:else if currentView === 'users'}
					<div class="user-list">
						{#each users as u (u.id)}
							<div class="user-row" class:inactive={!u.is_active}>
								<span class="user-name">{u.display_name}</span>
								<span class="user-email">{u.email}</span>
								<span
									class="user-role"
									class:role-patient={u.role === 'patient'}
									class:role-admin={u.role === 'admin'}
								>
									{u.role}
								</span>
								<span class="user-status">{u.is_active ? 'aktiv' : 'inaktiv'}</span>
							</div>
						{/each}
					</div>

					<h3 class="sub-heading">Neuen Benutzer anlegen</h3>

					<div class="field">
						<label>Email</label>
						<input type="email" bind:value={newUserEmail} placeholder="email@example.com" />
					</div>

					<div class="field">
						<label>Passwort</label>
						<input
							type="password"
							bind:value={newUserPassword}
							placeholder="Mindestens 6 Zeichen"
						/>
					</div>

					<div class="field-checkbox">
						<input
							type="checkbox"
							id="is-patient"
							bind:checked={newUserIsPatient}
							disabled={patientExists}
						/>
						<label for="is-patient">
							Patient
							{#if patientExists}
								<span class="hint-inline">(Es existiert bereits ein Patient)</span>
							{/if}
						</label>
					</div>

					{#if newUserError}
						<p class="error">{newUserError}</p>
					{/if}

					<button class="submit-btn" onclick={createUser} disabled={newUserLoading}>
						{newUserLoading ? 'Anlegen...' : 'Benutzer anlegen'}
					</button>
				{:else if currentView === 'ml'}
					<h3 class="sub-heading">ML Training</h3>
					<button
						class="submit-btn"
						onclick={startMlTrain}
						disabled={mlTrainStatus === 'starte…' || mlTrainStatus === 'running…'}
					>
						{mlTrainStatus ? mlTrainStatus : 'Training starten'}
					</button>
					{#if mlTrainResult?.metrics}
						<h4 class="sub-heading" style="margin-top:1rem">Ergebnisse</h4>
						{#each mlTrainResult.metrics as m}
							<p class="hint">
								Horizont {m.horizon}h: Baseline MAE {m.baseline_mae.toFixed(1)}, Modell MAE {m.model_mae.toFixed(
									1
								)}, Splits {m.n_splits}
							</p>
						{/each}
					{/if}

					<hr style="margin:1rem 0;border:none;border-top:1px solid var(--color-border)" />

					<h3 class="sub-heading">ML Evaluation</h3>
					<button
						class="submit-btn"
						onclick={startMlEvaluate}
						disabled={mlEvalStatus === 'starte…' || mlEvalStatus === 'running…'}
					>
						{mlEvalStatus ? mlEvalStatus : 'Evaluation starten'}
					</button>
					{#if mlEvalResult?.summaries}
						<h4 class="sub-heading" style="margin-top:1rem">Zusammenfassung</h4>
						{#each mlEvalResult.summaries as s}
							<p class="hint">
								Horizont {s.horizon}h (v{s.model_version}): MAE {s.mae.toFixed(1)}, {s.matched_points}
								Punkte, {s.completed_runs}/{s.run_count} Runs
							</p>
						{/each}
					{/if}
				{/if}

				{#if error}
					<p class="error">{error}</p>
				{/if}

				{#if message}
					<p class="success">{message}</p>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.settings-btn {
		background: transparent;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 8px;
		border-radius: var(--radius);
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s ease;
	}

	.settings-btn:hover {
		background: var(--color-bg);
		color: var(--color-text);
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
		padding: var(--spacing-md);
		overflow-y: auto;
	}

	.modal {
		background: var(--color-surface);
		border-radius: var(--radius);
		width: 100%;
		max-width: 420px;
		max-height: calc(100vh - 2rem);
		overflow-y: auto;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
		margin: auto;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--spacing-md);
		border-bottom: 1px solid var(--color-border);
	}

	.modal-header h2 {
		margin: 0;
		font-size: 1.1rem;
		color: var(--color-text);
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		font-size: 1.5rem;
		cursor: pointer;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius);
	}

	.close-btn:hover {
		background: var(--color-bg);
		color: var(--color-text);
	}

	.back-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		font-size: 1.8rem;
		line-height: 1;
		cursor: pointer;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius);
		margin-right: auto;
	}

	.back-btn:hover {
		background: var(--color-bg);
		color: var(--color-text);
	}

	.section-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.section-item {
		display: flex;
		align-items: center;
		gap: var(--spacing-md);
		width: 100%;
		padding: var(--spacing-sm) var(--spacing-md);
		background: transparent;
		border: none;
		border-radius: 0;
		color: var(--color-text);
		text-align: left;
		cursor: pointer;
		font-size: 0.95rem;
		transition: background 0.1s;
	}

	.section-item:first-child {
		border-radius: var(--radius) var(--radius) 0 0;
	}

	.section-item:last-child {
		border-radius: 0 0 var(--radius) var(--radius);
	}

	.section-item:hover {
		background: var(--color-bg);
	}

	.section-icon {
		font-size: 1.3rem;
		width: 28px;
		text-align: center;
	}

	.section-name {
		flex: 1;
	}

	.section-chevron {
		color: var(--color-text-muted);
		font-size: 1.4rem;
		line-height: 1;
	}

	.modal-body {
		padding: var(--spacing-md);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-md);
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.field label {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.field input {
		padding: var(--spacing-xs) var(--spacing-sm);
		font-size: 0.9rem;
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
	}

	.submit-btn {
		padding: var(--spacing-sm);
		font-size: 0.95rem;
		background: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
		border: none;
		border-radius: var(--radius);
		cursor: pointer;
		font-weight: 600;
	}

	.submit-btn:hover {
		background: var(--color-primary-dark);
	}

	.submit-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.logout-btn {
		margin-top: 0.5rem;
		padding: var(--spacing-sm);
		font-size: 0.95rem;
		background: transparent;
		color: #ef4444;
		border: 1px solid #ef4444;
		border-radius: var(--radius);
		cursor: pointer;
		font-weight: 600;
	}

	.logout-btn:hover {
		background: rgba(239, 68, 68, 0.1);
	}

	.user-list {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin-bottom: var(--spacing-md);
	}

	.user-row {
		display: grid;
		grid-template-columns: 1fr 1.5fr auto auto;
		gap: var(--spacing-sm);
		align-items: center;
		padding: var(--spacing-xs) var(--spacing-sm);
		background: var(--color-bg);
		border-radius: var(--radius);
		font-size: 0.85rem;
	}

	.user-row.inactive {
		opacity: 0.5;
	}

	.user-name {
		font-weight: 600;
		color: var(--color-text);
	}

	.user-email {
		color: var(--color-text-muted);
		font-size: 0.8rem;
	}

	.user-role {
		font-size: 0.7rem;
		padding: 2px 6px;
		border-radius: 4px;
		background: var(--color-border);
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.user-role.role-patient {
		background: rgba(var(--color-primary-rgb), 0.15);
		color: var(--color-primary);
	}

	.user-role.role-admin {
		background: rgba(249, 115, 22, 0.15);
		color: #f97316;
	}

	.user-status {
		font-size: 0.7rem;
		color: var(--color-text-muted);
	}

	.sub-heading {
		margin: var(--spacing-sm) 0;
		font-size: 0.9rem;
		color: var(--color-text);
	}

	.field-checkbox {
		display: flex;
		align-items: center;
		gap: var(--spacing-xs);
		padding: var(--spacing-xs) 0;
	}

	.field-checkbox input[type='checkbox'] {
		width: 18px;
		height: 18px;
		cursor: pointer;
	}

	.field-checkbox label {
		font-size: 0.85rem;
		color: var(--color-text);
		cursor: pointer;
		display: flex;
		gap: 6px;
		align-items: center;
	}

	.hint-inline {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.error {
		color: #f87171;
		font-size: 0.85rem;
		text-align: center;
		margin: 0;
	}

	.success {
		color: #4ade80;
		font-size: 0.85rem;
		text-align: center;
		margin: 0;
	}

	.loading {
		color: var(--color-text-muted);
		text-align: center;
		margin: 0;
	}

	.hint {
		color: var(--color-text-muted);
		font-size: 0.85rem;
		margin: 0;
	}

	.field select {
		padding: var(--spacing-xs) var(--spacing-sm);
		font-size: 0.9rem;
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius);
	}

	.button-row {
		display: flex;
		gap: var(--spacing-sm);
	}

	.button-row .submit-btn {
		flex: 1;
	}

	.test-btn {
		padding: var(--spacing-sm);
		font-size: 0.95rem;
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius);
		cursor: pointer;
		font-weight: 500;
	}

	.test-btn:hover:not(:disabled) {
		background: var(--color-border-subtle);
	}

	.test-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.field-row {
		display: flex;
		gap: var(--spacing-sm);
		align-items: center;
	}

	.field-row input {
		flex: 1;
		padding: var(--spacing-xs) var(--spacing-sm);
		font-size: 0.9rem;
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius);
	}

	.field-row .test-btn {
		white-space: nowrap;
	}

	.profile-list {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-sm);
	}

	.profile-item {
		background: var(--color-bg);
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius);
		overflow: hidden;
	}

	.profile-item.editing {
		border-color: var(--color-primary);
	}

	.profile-header {
		width: 100%;
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--spacing-sm) var(--spacing-md);
		background: transparent;
		color: var(--color-text);
		font-size: 0.95rem;
		font-weight: 500;
		cursor: pointer;
	}

	.profile-header:hover {
		background: var(--color-border-subtle);
	}

	.profile-name {
		text-align: left;
	}

	.profile-count {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		background: var(--color-surface);
		padding: 2px 8px;
		border-radius: var(--radius-pill);
	}

	.profile-editor {
		padding: var(--spacing-md);
		border-top: 1px solid var(--color-border-default);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-sm);
		background: var(--color-surface);
	}

	.row-fields {
		display: flex;
		gap: var(--spacing-sm);
		align-items: flex-end;
	}

	.row-fields .field.grow {
		flex: 1;
		min-width: 0;
	}

	.icon-row {
		display: flex;
		gap: var(--spacing-sm);
		align-items: center;
	}

	.icon-row .icon-suggestions {
		flex: 1;
	}

	.icon-input {
		font-size: 1.2rem;
		width: 80px;
		text-align: center;
		padding: var(--spacing-xs) var(--spacing-sm);
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius);
	}

	.icon-suggestions {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-top: 4px;
	}

	.icon-suggestion {
		width: 32px;
		height: 32px;
		font-size: 1.1rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border-default);
		border-radius: var(--radius);
		cursor: pointer;
		padding: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.icon-suggestion:hover {
		background: var(--color-border-subtle);
		border-color: var(--color-primary);
	}

	.webhook-row {
		display: flex;
		gap: var(--spacing-xs);
		align-items: center;
	}

	.webhook-input {
		flex: 1;
		font-family: ui-monospace, 'SF Mono', Menlo, monospace;
		font-size: 0.8rem;
		background: var(--color-bg);
		color: var(--color-text-muted);
	}

	.time-input {
		max-width: 120px;
	}

	.help-content {
		font-size: 0.9rem;
		line-height: 1.5;
		color: var(--color-text);
	}

	.help-content h3 {
		font-size: 1.05rem;
		margin: 1.25rem 0 0.5rem;
		color: var(--color-text);
	}

	.help-content h3:first-child {
		margin-top: 0;
	}

	.help-content ul {
		padding-left: 1.25rem;
		margin: 0.25rem 0 0.5rem;
	}

	.help-content li {
		margin-bottom: 0.3rem;
	}
	.color-row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.color-row input[type="color"] {
		width: 36px;
		height: 36px;
		padding: 2px;
		border: 1px solid var(--color-border-default);
		border-radius: 6px;
		cursor: pointer;
		background: none;
	}
	.color-row input[type="text"] {
		flex: 1;
	}
</style>
