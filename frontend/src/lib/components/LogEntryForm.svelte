<script lang="ts">
	import { createLog, fetchCarbFactor, fetchLogs, fetchGlobalSettings } from '$lib/api/log';
	import { apiFetch } from '$lib/auth';
	import { createPendingLogInputs, queuePendingLogEntries, type PendingLogInput } from '$lib/stores/pendingLogs';

	let {
		onsaved,
		currentBg = null as number | null
	}: { onsaved?: () => void; currentBg?: number | null } = $props();

	let open = $state(false);
	let activeTab = $state<'carbs' | 'insulin' | 'basal' | 'note'>('carbs');

	// Per-tab persisted state (only what user explicitly entered)
	let tabValues = $state<
		Record<string, { value: number | ''; correctionValue: number | ''; notes: string }>
	>({
		carbs: { value: '', correctionValue: '', notes: '' },
		insulin: { value: '', correctionValue: '', notes: '' },
		basal: { value: '', correctionValue: '', notes: '' },
		note: { value: '', correctionValue: '', notes: '' }
	});

	// Last basal value from DB for reference
	let lastBasalValue = $state<number | null>(null);
	// Last insulin entry for IOB warning
	let lastInsulinValue = $state<number | null>(null);
	let lastInsulinTime = $state<string | null>(null);
	// Carb factor for insulin calculation
	let carbFactor = $state<number | null>(null);
	// Correction factor for correction dose
	let correctionFactor = $state<number>(50);
	const TARGET_BG = 100;

	let value = $state<number | ''>('');
	let correctionValue = $state<number | ''>('');
	let notes = $state('');

	let loading = $state(false);
	let message = $state('');
	let error = $state('');

	// AI KE estimation
	let llmLoading = $state(false);
	let llmModalOpen = $state(false);
	let llmResult = $state<{ ke_value: number; reasoning: string; food_summary?: string } | null>(null);
	let llmError = $state('');

	// Photo upload for AI vision
	let photoData = $state<string | null>(null);
	let photoPreview = $state<string | null>(null);
	let fileInput: HTMLInputElement | undefined = $state();

	// Date/time state
	let dateStr = $state('');
	let timeStr = $state('');

	// Simulation prediction state
	let simulationResult = $state<Record<
		string,
		{
			status: string;
			points: { predicted_sgv: number; lower_bound: number; upper_bound: number }[];
		}
	> | null>(null);
	let simulationLoading = $state(false);
	let simulationTimer: ReturnType<typeof setTimeout> | null = null;

	async function updateSimulation() {
		const carbs = tabValues.carbs.value;
		const insulin = tabValues.insulin.value;
		if ((carbs === '' || carbs === 0) && (insulin === '' || insulin === 0)) {
			simulationResult = null;
			return;
		}
		simulationLoading = true;
		try {
			const res = await apiFetch('/api/dashboard/predict/simulate', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					carbs_grams: carbs === '' ? 0 : Number(carbs) * 10,
					insulin_units: insulin === '' ? 0 : Number(insulin)
				})
			});
			if (res.ok) {
				simulationResult = await res.json();
			}
		} catch {
			simulationResult = null;
		} finally {
			simulationLoading = false;
		}
	}

	async function estimateKe() {
		const hasPhoto = photoData !== null;
		if (!hasPhoto && !notes.trim()) return;
		llmLoading = true;
		llmError = '';
		llmResult = null;
		try {
			const body: Record<string, string> = {};
			if (hasPhoto && photoData) {
				body.image = photoData;
			}
			if (notes.trim()) {
				body.meal_description = notes;
			}
			const res = await apiFetch('/api/ai/estimate', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			if (res.ok) {
				llmResult = await res.json();
				llmModalOpen = true;
			} else {
				const err = await res.json().catch(() => ({}));
				llmError = err.error || err.detail || 'Unbekannter Fehler';
			}
		} catch {
			llmError = 'Keine Verbindung zum LLM-Server';
		} finally {
			llmLoading = false;
		}
	}

	function applyLlmdKe() {
		if (!llmResult) return;
		value = llmResult.ke_value;
		if (llmResult.food_summary) {
			notes = llmResult.food_summary;
		}
		activeTab = 'carbs';
		llmModalOpen = false;
		photoData = null;
		photoPreview = null;
		syncToTabValues();
	}

	function openCamera() {
		fileInput?.click();
	}

	async function handlePhotoSelected(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		// Reset input so same file can be re-selected
		input.value = '';

		// Show preview
		const reader = new FileReader();
		reader.onload = () => {
			photoPreview = reader.result as string;
		};
		reader.readAsDataURL(file);

		// Convert to base64 (without data: prefix)
		photoData = await new Promise<string>((resolve) => {
			const r = new FileReader();
			r.onload = () => {
				const dataUrl = r.result as string;
				resolve(dataUrl.split(',')[1]);
			};
			r.readAsDataURL(file);
		});
	}

	function clearPhoto() {
		photoData = null;
		photoPreview = null;
	}

	$effect(() => {
		// React to carbValue and insulinValue changes (accessed via tabValues)
		const _ = tabValues.carbs.value;
		const __ = tabValues.insulin.value;
		if (simulationTimer) clearTimeout(simulationTimer);
		simulationTimer = setTimeout(updateSimulation, 500);
		return () => {
			if (simulationTimer) clearTimeout(simulationTimer);
		};
	});

	const units: Record<string, string> = {
		carbs: 'KE',
		insulin: 'U',
		basal: 'U',
		note: ''
	};

	const tabLabels: Record<string, string> = {
		carbs: 'KE',
		insulin: 'Insulin',
		basal: 'Basal',
		note: 'Notiz'
	};

	function initNow() {
		const now = new Date();
		dateStr = now.toISOString().slice(0, 10);
		timeStr = now.toTimeString().slice(0, 5);
	}

	function getTimestamp(): string {
		return new Date(`${dateStr}T${timeStr}`).toISOString();
	}

	function isFuture(): boolean {
		return new Date(`${dateStr}T${timeStr}`).getTime() > Date.now();
	}

	function adjustTime(minutes: number) {
		const d = new Date(`${dateStr}T${timeStr}`);
		d.setMinutes(d.getMinutes() + minutes);
		dateStr = d.toISOString().slice(0, 10);
		timeStr = d.toTimeString().slice(0, 5);
	}

	function switchTab(tab: 'carbs' | 'insulin' | 'basal' | 'note') {
		// Save current tab values
		tabValues[activeTab] = { value, correctionValue, notes };
		// Switch
		activeTab = tab;
		// Load new tab values
		value = tabValues[tab].value;
		correctionValue = tabValues[tab].correctionValue;
		notes = tabValues[tab].notes;
		error = '';
	}

	function _tabHasValue(
		type: string,
		t: { value: number | ''; correctionValue: number | ''; notes: string }
	): boolean {
		if (type === 'note') return t.notes.trim() !== '';
		if (type === 'insulin') {
			return (t.value !== '' && t.value !== 0) || (t.correctionValue !== '' && Number(t.correctionValue) > 0);
		}
		return t.value !== '' && t.value !== 0;
	}

	function hasAnyValue(): boolean {
		return Object.entries(tabValues).some(([type, t]) => _tabHasValue(type, t));
	}

	// Reactive count of entries to save
	const entriesCount = $derived.by(() => {
		return Object.entries(tabValues).filter(([type, t]) => _tabHasValue(type, t)).length;
	});

	// Reactive insulin calculation hint
	const insulinHint = $derived.by(() => {
		if (activeTab !== 'insulin' || carbFactor === null) return null;
		const ke = tabValues.carbs.value;
		if (ke === '' || ke === 0) return null;
		const raw = Number(ke) * carbFactor;
		const insulin = Math.round(raw * 2) / 2;
		return { ke: Number(ke), factor: carbFactor, insulin };
	});

	function countEntriesToSave() {
		return Object.entries(tabValues).filter(([type, t]) => _tabHasValue(type, t)).length;
	}

	async function loadLastBasal() {
		const logs = await fetchLogs();
		const lastBasal = logs.find((l) => l.entry_type === 'basal');
		if (lastBasal) {
			lastBasalValue = lastBasal.value;
		}
	}

	function applyLastBasal() {
		if (lastBasalValue !== null) {
			value = lastBasalValue;
			tabValues.basal.value = lastBasalValue;
		}
	}

	async function loadLastInsulin() {
		const logs = await fetchLogs();
		const lastInsulin = logs.find((l) => l.entry_type === 'insulin');
		if (lastInsulin) {
			lastInsulinValue = lastInsulin.value;
			lastInsulinTime = lastInsulin.created_at;
		}
	}

	function applyLastInsulin() {
		if (lastInsulinValue !== null) {
			value = lastInsulinValue;
			tabValues.insulin.value = lastInsulinValue;
		}
	}

	function syncToTabValues() {
		tabValues[activeTab] = { value, correctionValue, notes };
	}

	function normalizeDecimal(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const raw = input.value.replace(',', '.');
		if (raw !== input.value) {
			input.value = raw;
		}
		syncToTabValues();
	}

	function isInsulinRecent(): boolean {
		if (!lastInsulinTime) return false;
		const hours = (Date.now() - new Date(lastInsulinTime).getTime()) / (1000 * 60 * 60);
		return hours < 4;
	}

	async function loadCarbFactor() {
		const data = await fetchCarbFactor();
		carbFactor = data?.current?.factor ?? 1;
	}

	async function loadGlobalSettings() {
		try {
			const data = await fetchGlobalSettings();
			correctionFactor = data?.correction_factor ?? 50;
		} catch {}
	}

	// Reactive correction suggestion: extra insulin to bring BG to TARGET_BG
	// Total insulin = meal suggestion (from carbs) + correction for BG
	// When user changes the insulin value, the correction auto-adjusts to keep the total balanced
	const correctionSuggestion = $derived.by(() => {
		if (currentBg === null || correctionFactor <= 0) return null;
		if (currentBg <= TARGET_BG) return null;
		const diff = currentBg - TARGET_BG;
		const correctionUnits = Math.round((diff / correctionFactor) * 2) / 2;
		const mealSuggestion = insulinHint?.insulin ?? 0;
		const totalUnits = mealSuggestion + correctionUnits;
		const mealDose = value === '' ? 0 : Number(value);
		const remaining = Math.max(0, Math.round((totalUnits - mealDose) * 2) / 2);
		return { diff, totalUnits, correctionUnits, remaining, factor: correctionFactor };
	});

	const expectedBgAfterCorrection = $derived.by(() => {
		if (currentBg === null || correctionFactor <= 0) return null;
		const dose = correctionValue === '' ? 0 : Number(correctionValue);
		return Math.round((currentBg as number) - dose * correctionFactor);
	});

	function applyCorrection() {
		if (correctionSuggestion) {
			correctionValue = correctionSuggestion.remaining;
		}
	}

	function applyCalculatedInsulin() {
		if (insulinHint) {
			value = insulinHint.insulin;
		}
	}

	function adjustValue(delta: number) {
		const current = value === '' ? 0 : Number(value);
		const next = Math.max(0, Math.round((current + delta) * 2) / 2);
		value = next === 0 ? '' : next;
		syncToTabValues();
	}

	function adjustCorrectionValue(delta: number) {
		const current = correctionValue === '' ? 0 : Number(correctionValue);
		const next = Math.max(0, Math.round((current + delta) * 2) / 2);
		correctionValue = next === 0 ? '' : next;
		syncToTabValues();
	}

	function validateValue(val: number | '', type: string): string | null {
		if (type === 'note') return null; // notes don't have a value
		if (val === '' || val === null || val === undefined) return null; // empty is ok, handled elsewhere
		const num = Number(val);
		if (num <= 0) return 'Wert muss positiv sein';
		if (type === 'carbs') {
			if (!Number.isFinite(num)) return 'Ungültiger Wert';
		}
		if (type === 'insulin' || type === 'basal') {
			// Only .0 or .5 allowed
			const frac = Math.round((num % 1) * 100) / 100;
			if (frac !== 0 && frac !== 0.5) return 'Nur in 0,5 Schritten';
		}
		return null;
	}

	function resetFormAfterSave() {
		tabValues = {
			carbs: { value: '', correctionValue: '', notes: '' },
			insulin: { value: '', correctionValue: '', notes: '' },
			basal: { value: '', correctionValue: '', notes: '' },
			note: { value: '', correctionValue: '', notes: '' }
		};
		value = '';
		correctionValue = '';
		notes = '';
		lastBasalValue = null;
		initNow();
		setTimeout(() => {
			message = '';
			open = false;
		}, 800);
	}

	function buildEntriesToPersist(
		entriesToSave: readonly [string, { value: number | ''; correctionValue: number | ''; notes: string }][],
		timestamp: string,
		hasCorrectionEntry: boolean
	): Omit<PendingLogInput, 'group_id' | 'sequence'>[] {
		const entries = entriesToSave
			.map(([type, data]) => ({
				entry_type: type as 'carbs' | 'insulin' | 'basal' | 'note',
				value: type === 'note' ? 0 : Number(data.value),
				unit: type === 'note' ? '' : units[type],
				notes: data.notes || null,
				created_at: timestamp
			}))
			.filter((entry) => !(hasCorrectionEntry && entry.entry_type === 'insulin' && entry.value === 0));

		if (hasCorrectionEntry) {
			const correctionNote = currentBg !== null
				? `Korrektur: BG ${currentBg} → Ziel ${TARGET_BG}`
				: 'Korrektur';
			entries.push({
				entry_type: 'insulin',
				value: Number(correctionValue),
				unit: units.insulin,
				notes: correctionNote,
				created_at: timestamp
			});
		}

		return entries;
	}

	function finishSuccessfulSave(successMessage: string) {
		message = successMessage;
		onsaved?.();
		resetFormAfterSave();
	}

	async function submit() {
		// Save current tab values first
		tabValues[activeTab] = { value, correctionValue, notes };

		if (!hasAnyValue()) {
			error = 'Bitte mindestens einen Wert eingeben.';
			return;
		}
		if (isFuture()) {
			error = 'Zeit darf nicht in der Zukunft liegen.';
			return;
		}

		// Validate all entries to save
		const toSave = Object.entries(tabValues).filter(([type, t]) => _tabHasValue(type, t));
		for (const [type, data] of toSave) {
			const validationError = validateValue(data.value, type);
			if (validationError) {
				error = `${tabLabels[type]}: ${validationError}`;
				activeTab = type as typeof activeTab;
				value = data.value;
				notes = data.notes;
				return;
			}
		}

		loading = true;
		error = '';
		message = '';

		const timestamp = getTimestamp();
		let saved = 0;
		let lastError: string | undefined;
		const hasCorrectionEntry = correctionValue !== '' && Number(correctionValue) > 0;
		const entriesToPersist = buildEntriesToPersist(toSave, timestamp, hasCorrectionEntry);
		const expectedSaveCount = entriesToPersist.length;

		if (typeof navigator !== 'undefined' && !navigator.onLine) {
			queuePendingLogEntries(createPendingLogInputs(entriesToPersist));
			finishSuccessfulSave(
				`${expectedSaveCount} Eintrag${expectedSaveCount > 1 ? 'e' : ''} offline gespeichert.`
			);
			loading = false;
			return;
		}

		for (let index = 0; index < entriesToPersist.length; index += 1) {
			const entry = entriesToPersist[index];
			try {
				const result = await createLog(
					entry.entry_type,
					entry.value,
					entry.unit,
					entry.notes ?? undefined,
					entry.created_at
				);
				if (result.entry) {
					saved++;
					continue;
				}

				lastError = `${tabLabels[entry.entry_type] ?? 'Eintrag'}: ${result.error ?? 'Fehler beim Speichern.'}`;
				break;
			} catch (error) {
				if (error instanceof Error) {
					const queuedEntries = queuePendingLogEntries(
						createPendingLogInputs(entriesToPersist.slice(index))
					);
					const queuedCount = queuedEntries.length;
					const successMessage =
						saved > 0
							? `${saved} Eintrag${saved > 1 ? 'e' : ''} gespeichert, ${queuedCount} offline vorgemerkt.`
							: `${queuedCount} Eintrag${queuedCount > 1 ? 'e' : ''} offline gespeichert.`;
					finishSuccessfulSave(successMessage);
					loading = false;
					return;
				}
				throw error;
			}
		}

		if (saved === expectedSaveCount) {
			finishSuccessfulSave(
				`${expectedSaveCount} Eintrag${expectedSaveCount > 1 ? 'e' : ''} gespeichert.`
			);
		} else {
			error = lastError || 'Fehler beim Speichern.';
		}
		loading = false;
	}

	function openModal() {
		open = true;
		initNow();
		activeTab = 'carbs';
		tabValues = {
			carbs: { value: '', correctionValue: '', notes: '' },
			insulin: { value: '', correctionValue: '', notes: '' },
			basal: { value: '', correctionValue: '', notes: '' },
			note: { value: '', correctionValue: '', notes: '' }
		};
		value = '';
		correctionValue = '';
		notes = '';
		loadCarbFactor();
		loadGlobalSettings();
		value = '';
		notes = '';
		error = '';
		message = '';
		lastBasalValue = null;
		lastInsulinValue = null;
		lastInsulinTime = null;
		carbFactor = null;
		loadLastBasal();
		loadLastInsulin();
		loadCarbFactor();
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') open = false;
	}
</script>

<svelte:window onkeydown={onKeydown} />

	<button class="add-btn" type="button" onclick={() => openModal()} title="Neuen Eintrag">+</button>

<!-- Modal -->
<!-- Hidden file input for photo upload -->
<input
	type="file"
	accept="image/*"
	capture="environment"
	style="display: none"
	bind:this={fileInput}
	onchange={handlePhotoSelected}
/>

{#if open}
	<div
		class="modal-backdrop"
		onclick={(e) => {
			if (e.target === e.currentTarget) open = false;
		}}
	>
		<div class="modal">
			<div class="modal-header">
				<h2>Neuer Eintrag</h2>
				<button class="close-btn" onclick={() => (open = false)}>×</button>
			</div>

			<!-- Tabs -->
			<div class="tabs">
				{#each Object.entries(tabLabels) as [key, label]}
					<button
						class="tab"
						class:active={activeTab === key}
						class:has-value={tabValues[key].value !== ''}
						onclick={() => switchTab(key as typeof activeTab)}
					>
						{label}
						{#if tabValues[key].value !== ''}
							<span class="tab-badge">{tabValues[key].value}</span>
						{/if}
					</button>
				{/each}
			</div>

			<div class="modal-body">
				<div class="datetime-row">
					<div class="field">
						<label>Datum</label>
						<input type="date" bind:value={dateStr} />
						<div class="time-buttons-inline">
							<button class="time-btn" onclick={() => adjustTime(-5)}>−5m</button>
							<button class="time-btn" onclick={() => adjustTime(-1)}>−1m</button>
						</div>
						{#if activeTab === 'insulin'}
							<label class="value-label">Insulin (U)</label>
							<div class="value-input-row">
								<input
									type="text"
									inputmode="decimal"
									enterkeyhint="done"
									pattern="[0-9]*"
									bind:value
									oninput={normalizeDecimal}
									min="0"
									step="0.5"
									placeholder="0"
								/>
								<button type="button" class="adjust-btn" onclick={() => adjustValue(-0.5)}>−</button
								>
								<button type="button" class="adjust-btn" onclick={() => adjustValue(0.5)}>+</button>
							</div>
						{:else if activeTab === 'carbs'}
							<label class="value-label">KE</label>
							<div class="value-input-row">
								<input
									type="text"
									inputmode="decimal"
									enterkeyhint="done"
									bind:value
									oninput={normalizeDecimal}
									min="0"
									step="0.1"
									placeholder="0"
								/>
							</div>
						{:else if activeTab === 'basal'}
							<label class="value-label">Basal (U)</label>
							<div class="value-input-row">
								<input
									type="text"
									inputmode="decimal"
									enterkeyhint="done"
									bind:value
									oninput={normalizeDecimal}
									min="0"
									step="0.5"
									placeholder="0"
								/>
								<button type="button" class="adjust-btn" onclick={() => adjustValue(-0.5)}>−</button
								>
								<button type="button" class="adjust-btn" onclick={() => adjustValue(0.5)}>+</button>
							</div>
							{#if lastBasalValue !== null}
								<button class="last-value-hint" onclick={applyLastBasal}>
									Letzter Wert: {lastBasalValue} U → übernehmen
								</button>
							{/if}
						{/if}
					</div>
					<div class="field">
						<label>Uhrzeit</label>
						<input type="time" bind:value={timeStr} />
						<div class="time-buttons-inline">
							<button class="time-btn" onclick={() => adjustTime(1)}>+1m</button>
							<button class="time-btn" onclick={() => adjustTime(5)}>+5m</button>
						</div>
						{#if activeTab === 'insulin'}
							<label class="value-label">Korrektur (U)</label>
							<div class="value-input-row">
								<input
									type="text"
									inputmode="decimal"
									bind:value={correctionValue}
									oninput={normalizeDecimal}
									step="0.5"
									min="0"
									placeholder="0"
									class="correction-input"
								/>
								<button type="button" class="adjust-btn" onclick={() => adjustCorrectionValue(-0.5)}
									>−</button
								>
								<button type="button" class="adjust-btn" onclick={() => adjustCorrectionValue(0.5)}
									>+</button
								>
							</div>
						{/if}
					</div>
				</div>

				{#if isFuture()}
					<div class="validation-error">Zeit liegt in der Zukunft</div>
				{/if}

				{#if activeTab === 'note'}
					<div class="field note-field">
						<div class="note-label-row">
							<label>Notiz</label>
							<div class="ai-btn-group">
								<button
									class="ai-btn"
									type="button"
									onclick={estimateKe}
									disabled={llmLoading || (!notes.trim() && !photoData)}
									title="KI-gestützte KE-Schätzung aus Notiztext"
								>
									{#if llmLoading}
										<span class="ai-spinner"></span>
									{:else}
										🤖 KI
									{/if}
								</button>
								<button
									class="ai-btn"
									type="button"
									onclick={openCamera}
									disabled={llmLoading}
									title="Foto der Mahlzeit analysieren"
								>
									📷
								</button>
							</div>
						</div>
						{#if photoPreview}
							<div class="photo-preview-wrap">
								<img class="photo-preview" src={photoPreview} alt="Vorschau" />
								<button class="photo-clear-btn" type="button" onclick={clearPhoto}>×</button>
							</div>
						{/if}
						<textarea
							bind:value={notes}
							oninput={syncToTabValues}
							placeholder="Notiz eingeben..."
							rows="4"
						></textarea>
						{#if llmError}
							<span class="llm-error">{llmError}</span>
						{/if}
					</div>
				{:else if activeTab === 'insulin'}
					{#if insulinHint}
						<button class="last-value-hint calc-hint" onclick={applyCalculatedInsulin}>
							{insulinHint.ke} KE × {insulinHint.factor} = {insulinHint.insulin}
							{units.insulin} → übernehmen
						</button>
					{/if}
					{#if correctionSuggestion}
						<button class="last-value-hint correction-hint" onclick={applyCorrection}>
							Korrektur übernehmen: {correctionSuggestion.remaining}
							{units.insulin} (Total {correctionSuggestion.totalUnits} − eingegeben {value === ''
								? 0
								: Number(value)})
						</button>
						{#if expectedBgAfterCorrection !== null && currentBg !== null}
							<p class="correction-target">
								Erwarteter BG: <strong>{expectedBgAfterCorrection} mg/dL</strong>
								<span class="correction-diff"
									>({currentBg > expectedBgAfterCorrection ? '−' : '+'}{Math.abs(
										Math.round((currentBg - expectedBgAfterCorrection) * 10) / 10
									)})</span
								>
							</p>
						{/if}
					{/if}
					<div class="field">
						<label>Notizen</label>
						<input
							type="text"
							bind:value={notes}
							oninput={syncToTabValues}
							placeholder="Optional"
						/>
					</div>
				{:else}
					<div class="field">
						<div class="note-label-row">
							<label>Notizen</label>
							<div class="ai-btn-group">
								<button
									class="ai-btn"
									type="button"
									onclick={estimateKe}
									disabled={llmLoading || (!notes.trim() && !photoData)}
									title="KI-gestützte KE-Schätzung aus Notiztext"
								>
									{#if llmLoading}
										<span class="ai-spinner"></span>
									{:else}
										🤖 KI
									{/if}
								</button>
								<button
									class="ai-btn"
									type="button"
									onclick={openCamera}
									disabled={llmLoading}
									title="Foto der Mahlzeit analysieren"
								>
									📷
								</button>
							</div>
						</div>
						{#if photoPreview}
							<div class="photo-preview-wrap">
								<img class="photo-preview" src={photoPreview} alt="Vorschau" />
								<button class="photo-clear-btn" type="button" onclick={clearPhoto}>×</button>
							</div>
						{/if}
						<input
							type="text"
							bind:value={notes}
							oninput={syncToTabValues}
							placeholder="Optional"
						/>
						{#if llmError}
							<span class="llm-error">{llmError}</span>
						{/if}
					</div>
				{/if}

				{#if value !== '' && validateValue(value, activeTab)}
					<div class="validation-error">{validateValue(value, activeTab)}</div>
				{/if}

				<!-- Simulation forecast preview -->
				{#if simulationResult && !simulationLoading}
					<div class="forecast-bar">
						<span class="forecast-label">📈</span>
						{#each Object.entries(simulationResult) as [key, data], i}
							{#if data.points?.[0]?.predicted_sgv}
								{@const sgv = data.points[0].predicted_sgv}
								<span
									class="forecast-value"
									class:forecast-green={sgv >= 70 && sgv <= 180}
									class:forecast-yellow={sgv > 180 && sgv <= 250}
									class:forecast-red={sgv < 70 || sgv > 250}
								>
									{i > 0 ? ' | ' : ''}{key}min: {sgv}
								</span>
							{/if}
						{/each}
					</div>
				{/if}

				<button
					class="submit-btn"
					onclick={submit}
					disabled={loading || countEntriesToSave() === 0 || isFuture()}
				>
					{#if loading}
						Speichern...
					{:else if countEntriesToSave() > 1}
						{countEntriesToSave()} Einträge speichern
					{:else}
						Speichern
					{/if}
				</button>

				{#if message}
					<div class="success">{message}</div>
				{/if}
				{#if error}
					<div class="error">{error}</div>
				{/if}
			</div>
		</div>
	</div>
{/if}

{#if llmModalOpen && llmResult}
	<button class="llm-modal-backdrop" type="button" onclick={() => (llmModalOpen = false)}></button>
	<div class="llm-modal">
		<header class="llm-modal-header">
			<h3>KI KE-Schätzung</h3>
			<button class="close-btn" type="button" onclick={() => (llmModalOpen = false)}>×</button>
		</header>
		<div class="llm-modal-body">
			<div class="llm-value">
				<span class="llm-value-label">Geschätzter KE-Wert:</span>
				<span class="llm-value-number">{llmResult.ke_value.toFixed(1)} KE</span>
			</div>
			{#if llmResult.food_summary}
				<div class="llm-food-summary">
					<span class="llm-reasoning-label">Erkannte Mahlzeit:</span>
					<p>{llmResult.food_summary}</p>
				</div>
			{/if}
			<div class="llm-reasoning">
				<span class="llm-reasoning-label">Begründung:</span>
				<p>{llmResult.reasoning}</p>
			</div>
		</div>
		<div class="llm-modal-actions">
			<button class="llm-cancel-btn" type="button" onclick={() => (llmModalOpen = false)}>Abbrechen</button>
			<button class="llm-accept-btn" type="button" onclick={applyLlmdKe}>Übernehmen</button>
		</div>
	</div>
{/if}

<style>
	.add-btn {
		position: fixed;
		left: 50%;
		bottom: calc(env(safe-area-inset-bottom, 0px) + var(--spacing-md));
		z-index: 100;
		transform: translateX(-50%);
		width: 60px;
		height: 60px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: var(--spacing-xs);
		border-radius: 50%;
		background: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
		font-size: 1.75rem;
		font-weight: 700;
		border: none;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.3);
		transition:
			transform 0.15s ease,
			box-shadow 0.15s ease;
	}


	.add-btn:hover {
		transform: translateX(-50%) scale(1.1);
		box-shadow: 0 4px 12px rgba(var(--color-primary-rgb), 0.4);
	}

	.add-btn:active {
		transform: translateX(-50%) scale(0.95);
	}

	@media (max-width: 480px) {
		.add-btn {
			width: 60px;
			padding: 0;
		}
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

	.tabs {
		display: flex;
		padding: var(--spacing-sm);
		gap: var(--spacing-xs);
		border-bottom: 1px solid var(--color-border);
	}

	.tab {
		flex: 1;
		padding: var(--spacing-xs) var(--spacing-sm);
		background: transparent;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		color: var(--color-text-muted);
		font-size: 0.85rem;
		cursor: pointer;
		transition: all 0.15s ease;
		position: relative;
	}

	.tab.active {
		background: var(--color-primary);
		border-color: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
	}

	.tab.has-value:not(.active) {
		background: rgba(var(--color-primary-rgb), 0.1);
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	.tab:hover:not(.active) {
		background: var(--color-bg);
	}

	.tab-badge {
		margin-left: 4px;
		font-size: 0.7rem;
		background: rgba(255, 255, 255, 0.2);
		padding: 1px 4px;
		border-radius: 4px;
	}

	.modal-body {
		padding: var(--spacing-md);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-md);
	}

	.datetime-row {
		display: flex;
		gap: var(--spacing-sm);
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex: 1;
		min-width: 0;
	}

	.field label {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.value-label {
		margin-top: var(--spacing-xs);
	}

	.field input {
		padding: 4px 6px;
		font-size: 0.8rem;
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
	}

	.value-field {
		position: relative;
	}

	.value-field input {
		font-size: 0.8rem;
		padding: 4px 6px;
	}

	.correction-input {
		border-color: #f97316;
	}

	.correction-input:focus {
		border-color: #f97316;
		outline-color: rgba(249, 115, 22, 0.3);
	}

	.correction-target {
		margin: 4px 0 0;
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.correction-target strong {
		color: var(--color-text);
	}

	.correction-diff {
		margin-left: 4px;
		font-variant-numeric: tabular-nums;
		opacity: 0.7;
	}

	.value-input-row {
		display: flex;
		gap: 4px;
		align-items: center;
	}

	.value-input-row.insulin-row {
		gap: var(--spacing-sm);
		align-items: flex-end;
	}

	.value-input-row input {
		flex: 1;
		min-width: 0;
	}

	.correction-inline {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex: 1;
		min-width: 0;
	}

	.correction-inline input {
		width: 100%;
	}

	.correction-row {
		display: flex;
		gap: 4px;
		align-items: center;
	}

	.correction-row input {
		flex: 1;
		min-width: 0;
	}

	.correction-label {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.adjust-btn {
		flex-shrink: 0;
		padding: 4px 6px;
		font-size: 0.8rem;
		font-weight: 600;
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		cursor: pointer;
		min-width: 28px;
		touch-action: manipulation;
		transition: all 0.15s ease;
	}

	.adjust-btn:hover {
		background: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
		border-color: var(--color-primary);
	}

	.adjust-btn:active {
		transform: scale(0.95);
	}

	.note-field textarea {
		width: 100%;
		padding: var(--spacing-sm);
		font-size: 0.95rem;
		font-family: inherit;
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		resize: vertical;
		min-height: 80px;
	}

	.last-value-hint {
		margin-top: 4px;
		padding: var(--spacing-xs) var(--spacing-sm);
		font-size: 0.8rem;
		background: rgba(var(--color-primary-rgb), 0.1);
		border: 1px dashed var(--color-primary);
		border-radius: var(--radius);
		color: var(--color-primary);
		cursor: pointer;
		text-align: left;
		width: fit-content;
	}

	.last-value-hint:hover {
		background: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
		border-style: solid;
	}

	.last-value-hint.warning {
		background: rgba(234, 179, 8, 0.1);
		border-color: #eab308;
		color: #eab308;
	}

	.last-value-hint.warning:hover {
		background: #eab308;
		color: white;
		border-style: solid;
	}

	.last-value-hint.calc-hint {
		background: rgba(59, 130, 246, 0.1);
		border-color: #3b82f6;
		color: #3b82f6;
	}

	.last-value-hint.correction-hint {
		background: rgba(249, 115, 22, 0.1);
		border-color: #f97316;
		color: #f97316;
	}

	.last-value-hint.calc-hint:hover {
		background: #3b82f6;
		color: white;
		border-style: solid;
	}

	.warn-icon {
		width: 14px;
		height: 14px;
		vertical-align: middle;
		margin-right: 4px;
	}

	.warn-text {
		font-size: 0.75rem;
		opacity: 0.9;
		margin-left: 4px;
	}

	.time-buttons {
		display: flex;
		gap: var(--spacing-xs);
	}

	.time-buttons-inline {
		display: flex;
		gap: var(--spacing-xs);
		margin-top: var(--spacing-xs);
	}

	.time-btn {
		flex: 1;
		min-height: 36px;
		padding: 3px 0;
		font-size: 0.7rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.time-btn:hover {
		background: var(--color-surface);
		color: var(--color-text);
	}

	.time-btn:active {
		background: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
		border-color: var(--color-primary);
	}

	.validation-error {
		color: #f87171;
		font-size: 0.8rem;
		text-align: center;
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

	.submit-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.submit-btn:not(:disabled):hover {
		filter: brightness(1.1);
	}

	.success {
		color: #4ade80;
		font-size: 0.85rem;
		text-align: center;
	}

	.error {
		color: #f87171;
		font-size: 0.85rem;
		text-align: center;
	}

	.forecast-bar {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 6px 8px;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: 0.8rem;
		flex-wrap: wrap;
	}

	.forecast-label {
		font-size: 0.9rem;
		margin-right: 2px;
	}

	.forecast-value {
		font-variant-numeric: tabular-nums;
	}

	.forecast-green {
		color: #4ade80;
	}

	.forecast-yellow {
		color: #eab308;
	}

	.forecast-red {
		color: #f87171;
	}

	/* AI Button */
	.note-label-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.note-label-row label {
		margin: 0;
	}
	.ai-btn {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 8px;
		font-size: 0.8rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		color: var(--color-primary);
		cursor: pointer;
		transition: background 0.15s;
	}
	.ai-btn:hover:not(:disabled) {
		background: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
	}
	.ai-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.ai-spinner {
		display: inline-block;
		width: 12px;
		height: 12px;
		border: 2px solid var(--color-border);
		border-top-color: var(--color-primary);
		border-radius: 50%;
		animation: ai-spin 0.6s linear infinite;
	}
	@keyframes ai-spin {
		to { transform: rotate(360deg); }
	}
	.llm-error {
		color: #e53e3e;
		font-size: 0.75rem;
		margin-top: 2px;
	}

	/* LLM Result Modal */
	.llm-modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 150;
		border: none;
		padding: 0;
		margin: 0;
		cursor: pointer;
		appearance: none;
	}
	.llm-modal {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: min(90vw, 420px);
		max-height: 80vh;
		background: var(--color-surface);
		border-radius: var(--radius-lg, 20px);
		z-index: 151;
		padding: var(--spacing-lg, 24px);
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-md);
		overflow-y: auto;
	}
	.llm-modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.llm-modal-header h3 {
		margin: 0;
		font-size: 1.1rem;
	}
	.llm-modal-body {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-sm);
	}
	.llm-value {
		display: flex;
		align-items: baseline;
		gap: var(--spacing-sm);
		padding: var(--spacing-sm);
		background: color-mix(in srgb, var(--color-primary) 10%, transparent);
		border-radius: var(--radius);
	}
	.llm-value-label {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}
	.llm-value-number {
		font-size: 1.3rem;
		font-weight: 700;
		color: var(--color-primary);
	}
	.llm-reasoning {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.llm-reasoning-label {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		font-weight: 600;
	}
	.llm-reasoning p {
		margin: 0;
		font-size: 0.9rem;
		line-height: 1.5;
		color: var(--color-text);
	}
	.llm-modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: var(--spacing-sm);
		padding-top: var(--spacing-sm);
		border-top: 1px solid var(--color-border);
	}
	.llm-cancel-btn {
		padding: var(--spacing-xs) var(--spacing-md);
		font-size: 0.9rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: transparent;
		color: var(--color-text);
		cursor: pointer;
	}
	.llm-cancel-btn:hover {
		background: var(--color-border);
	}
	.llm-accept-btn {
		padding: var(--spacing-xs) var(--spacing-md);
		font-size: 0.9rem;
		border: none;
		border-radius: var(--radius);
		background: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
		cursor: pointer;
		font-weight: 600;
	}
	.llm-accept-btn:hover {
		opacity: 0.9;
	}

	/* AI button group (AI + Camera) */
	.ai-btn-group {
		display: flex;
		gap: 4px;
	}

	/* Photo preview */
	.photo-preview-wrap {
		position: relative;
		margin-top: var(--spacing-xs);
		border-radius: var(--radius);
		overflow: hidden;
		max-width: 200px;
	}
	.photo-preview {
		display: block;
		width: 100%;
		height: auto;
		border-radius: var(--radius);
	}
	.photo-clear-btn {
		position: absolute;
		top: 4px;
		right: 4px;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		border: none;
		background: rgba(0, 0, 0, 0.6);
		color: #fff;
		font-size: 14px;
		line-height: 1;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	/* Food summary in LLM modal */
	.llm-food-summary {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: var(--spacing-sm);
		background: color-mix(in srgb, var(--color-primary) 5%, transparent);
		border-radius: var(--radius);
		border-left: 3px solid var(--color-primary);
	}
	.llm-food-summary p {
		margin: 0;
		font-size: 0.9rem;
		line-height: 1.5;
		color: var(--color-text);
		font-style: italic;
	}
</style>
