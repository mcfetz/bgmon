<script lang="ts">
	import { deleteLog, fetchLogsRange, type LogEntry } from '$lib/api/log';
	import { sortLogsByCreatedAtDesc, type PendingLogEntry } from '$lib/stores/pendingLogs';

	let {
		refreshTrigger = 0,
		windowStart,
		windowEnd,
		highlightedTimestamp,
		onHighlight,
		filters = { carbs: true, insulin: true, basal: true, alarm: false, note: true },
		pendingLogs = [] as readonly PendingLogEntry[]
	}: {
		refreshTrigger?: number;
		windowStart: Date;
		windowEnd: Date;
		highlightedTimestamp: string | null;
		onHighlight: (ts: string | null) => void;
		filters: { carbs: boolean; insulin: boolean; basal: boolean; alarm: boolean; note: boolean };
		pendingLogs?: readonly PendingLogEntry[];
	} = $props();

	let logs = $state<LogEntry[]>([]);
	let deleteConfirmation = $state<LogEntry | null>(null);
	let filterOpen = $state(false);
	let historyExpanded = $state(true);

	async function loadLogs() {
		const startIso = windowStart.toISOString();
		const endIso = windowEnd.toISOString();
		logs = await fetchLogsRange(startIso, endIso);
	}

	$effect(() => {
		// Read reactive deps so $effect tracks them, then reload.
		void refreshTrigger;
		void windowStart;
		void windowEnd;
		loadLogs();
	});

	async function remove(id: number) {
		const ok = await deleteLog(id);
		if (ok) {
			logs = logs.filter((l) => l.id !== id);
			deleteConfirmation = null;
		}
	}

	function confirmDelete(): void {
		if (deleteConfirmation) void remove(deleteConfirmation.id);
	}

	const visiblePendingLogs = $derived(
		pendingLogs.filter((log) => {
			const timestamp = new Date(log.created_at).getTime();
			return timestamp >= windowStart.getTime() && timestamp <= windowEnd.getTime();
		})
	);

	const mergedLogs = $derived(sortLogsByCreatedAtDesc([...logs, ...visiblePendingLogs]));

	const filteredLogs = $derived(
		mergedLogs.filter((log) => {
			if (log.entry_type === 'carbs') return filters.carbs;
			if (log.entry_type === 'insulin') return filters.insulin;
			if (log.entry_type === 'basal') return filters.basal;
			if (log.entry_type === 'alarm') return filters.alarm;
			if (log.entry_type === 'note' || log.entry_type === 'success') return filters.note;
			return true;
		})
	);

	const groupedLogs = $derived.by(() => {
		const groups: { dateLabel: string; logs: typeof filteredLogs }[] = [];

		for (const log of filteredLogs) {
			const dateLabel = formatDateHeading(log.created_at);
			const lastGroup = groups[groups.length - 1];
			if (lastGroup?.dateLabel === dateLabel) {
				lastGroup.logs.push(log);
			} else {
				groups.push({ dateLabel, logs: [log] });
			}
		}

		return groups;
	});

	function typeIcon(type: string): string {
		const icons: Record<string, string> = {
			carbs: '🥪',
			insulin: '💉',
			basal: '💉',
			note: '📝',
			alarm: '🔔',
			success: '🏆'
		};
		return icons[type] ?? '•';
	}

	function formatEntry(log: LogEntry): string {
		let text: string;
		if (log.entry_type === 'carbs') {
			text = `${log.value} ${log.unit} Kohlenhydrate gegessen.`;
		} else {
			const unit = log.value === 1 ? 'Einheit' : 'Einheiten';
			const label = log.entry_type === 'insulin' ? 'Insulin' : 'Basal';
			text = `${log.value} ${unit} ${label} gespritzt.`;
		}
		if (log.created_by) {
			text += ` (${log.created_by})`;
		}
		return text;
	}

	function formatTime(ts: string): string {
		return new Date(ts).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
	}

	function formatDateHeading(ts: string): string {
		const date = new Date(ts);
		const today = new Date();
		const yesterday = new Date(today);
		yesterday.setDate(today.getDate() - 1);

		if (date.toDateString() === today.toDateString()) return 'Heute';
		if (date.toDateString() === yesterday.toDateString()) return 'Gestern';

		return date.toLocaleDateString('de-DE', {
			weekday: 'long',
			day: '2-digit',
			month: 'long'
		});
	}

	function isPendingLog(log: LogEntry & { sync_state?: 'pending' | 'syncing' }): boolean {
		return log.sync_state === 'pending' || log.sync_state === 'syncing';
	}
</script>

{#if mergedLogs.length > 0}
	<div class="history">
		<div class="history-header">
			<button
				class="history-toggle"
				type="button"
				aria-expanded={historyExpanded}
				onclick={() => (historyExpanded = !historyExpanded)}
			>
				<span>Logbuch</span>
				<span class="history-count">{filteredLogs.length}</span>
				<svg
					class:collapsed={!historyExpanded}
					width="16"
					height="16"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<polyline points="6 9 12 15 18 9"></polyline>
				</svg>
			</button>
			<button class="filter-btn" onclick={() => (filterOpen = !filterOpen)} title="Filtern">
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
				</svg>
			</button>
		</div>
		{#if historyExpanded && filterOpen}
			<div class="filter-overlay" onclick={() => (filterOpen = false)}></div>
			<div class="filter-popover">
				{#each [
					{ key: 'carbs', label: 'Kohlenhydrate', icon: '🥪' },
					{ key: 'insulin', label: 'Insulin', icon: '💉' },
					{ key: 'basal', label: 'Basal', icon: '💉' },
					{ key: 'alarm', label: 'Alarm', icon: '🔔' },
					{ key: 'note', label: 'Notizen', icon: '📝' }
				] as item}
					<label class="filter-item">
						<span class="filter-icon">{item.icon}</span>
						<span class="filter-label">{item.label}</span>
						<input
							type="checkbox"
							checked={filters[item.key as keyof typeof filters]}
							onchange={() => (filters[item.key as keyof typeof filters] = !filters[item.key as keyof typeof filters])}
						/>
					</label>
				{/each}
			</div>
		{/if}
		{#if historyExpanded}
		<ul>
			{#each groupedLogs as group}
				<li class="date-heading">{group.dateLabel}</li>
				{#each group.logs as log}
					<li
					class:active={highlightedTimestamp === log.created_at}
					onmouseenter={() => onHighlight(log.created_at)}
					onmouseleave={() => onHighlight(null)}
					onclick={() =>
						onHighlight(highlightedTimestamp === log.created_at ? null : log.created_at)}
					>
						<span class="icon">{typeIcon(log.entry_type)}</span>
						<span class="time">{formatTime(log.created_at)}</span>
					{#if isPendingLog(log)}
						<span class="sync-badge">offline</span>
					{/if}
					{#if log.entry_type === 'note' || log.entry_type === 'alarm' || log.entry_type === 'success'}
						<span class="notes-note">{log.notes ?? ''}</span>
					{:else}
						<span class="value">{formatEntry(log)}</span>
						{#if log.notes}
							<span class="notes">— {log.notes}</span>
						{/if}
					{/if}
					<span class="actions">
						{#if isPendingLog(log)}
							<span class="pending-text">Wird synchronisiert…</span>
						{:else if highlightedTimestamp === log.created_at}
							<button
								class="delete-btn"
								onclick={(event) => {
									event.stopPropagation();
									deleteConfirmation = log;
								}}
								title="Löschen"
								>×</button
							>
						{/if}
					</span>
					</li>
				{/each}
			{/each}
		</ul>
		{/if}
	</div>
{/if}

{#if deleteConfirmation}
	<div class="delete-modal-backdrop" role="presentation" onclick={() => (deleteConfirmation = null)}>
		<div class="delete-modal" role="dialog" aria-modal="true" aria-labelledby="delete-modal-title" onclick={(event) => event.stopPropagation()}>
			<h3 id="delete-modal-title">Eintrag löschen?</h3>
			<p>{formatEntry(deleteConfirmation)}</p>
			<div class="delete-modal-actions">
				<button class="delete-modal-cancel" type="button" onclick={() => (deleteConfirmation = null)}>
					Abbrechen
				</button>
				<button class="delete-modal-confirm" type="button" onclick={confirmDelete}>
					Löschen
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.history {
		background: var(--color-surface);
		padding: var(--spacing-md);
		border-radius: var(--radius);
		position: relative;
	}

	.history ul {
		max-height: 350px;
		overflow-y: auto;
	}

	.history-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: var(--spacing-sm);
	}

	.history-toggle {
		display: flex;
		align-items: center;
		gap: var(--spacing-xs);
		min-height: 44px;
		padding: 0;
		background: transparent;
		color: var(--color-text-muted);
		font-size: 0.9rem;
		font-weight: 700;
	}

	.history-count {
		display: grid;
		place-items: center;
		min-width: 1.5rem;
		height: 1.5rem;
		border-radius: var(--radius-pill);
		background: var(--color-border-subtle);
		font-size: 0.75rem;
		font-variant-numeric: tabular-nums;
	}

	.history-toggle svg {
		transition: transform 150ms ease-out;
	}

	.history-toggle svg.collapsed {
		transform: rotate(-90deg);
	}

	.history-toggle:hover:not(:disabled),
	.history-toggle:active {
		background: transparent;
		color: var(--color-text-muted);
		transform: none;
	}


	.filter-btn {
		background: none;
		border: none;
		font-size: 1.1rem;
		cursor: pointer;
		color: var(--color-text-muted);
		padding: 2px 4px;
		border-radius: 4px;
		line-height: 1;
	}

	.filter-btn:hover {
		background: rgba(255, 255, 255, 0.1);
		color: var(--color-text);
	}

	.filter-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.3);
		z-index: 49;
	}

	.filter-popover {
		position: absolute;
		right: var(--spacing-md);
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.5rem;
		z-index: 50;
		box-shadow: 0 4px 12px rgba(0,0,0,0.15);
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 180px;
	}

	.filter-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.3rem 0.5rem;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.85rem;
	}

	.filter-item:hover {
		background: rgba(255, 255, 255, 0.05);
	}

	.filter-icon {
		font-size: 1rem;
		width: 20px;
		text-align: center;
	}

	.filter-label {
		flex: 1;
	}

	.filter-item input {
		accent-color: var(--color-primary);
	}

	.history ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: var(--spacing-xs);
	}

	.history li {
		position: relative;
		display: flex;
		gap: var(--spacing-sm);
		align-items: center;
		font-size: 0.85rem;
		padding: var(--spacing-xs) 44px var(--spacing-xs) 0;
		border-bottom: 1px solid var(--color-border);
		cursor: pointer;
	}

	.history .date-heading {
		display: block;
		padding: var(--spacing-md) 0 var(--spacing-xs);
		border: 0;
		color: var(--color-text-muted);
		font-size: 0.875rem;
		font-weight: 700;
		text-transform: capitalize;
	}

	.history li:hover {
		background: rgba(var(--color-primary-rgb), 0.05);
	}

	.history li.active {
		background: rgba(var(--color-primary-rgb), 0.1);
		box-shadow: inset 3px 0 0 var(--color-primary);
	}

	.history .icon {
		font-size: 1.1rem;
		min-width: 24px;
		text-align: center;
	}

	.history .time {
		color: var(--color-text-muted);
		min-width: 42px;
		font-variant-numeric: tabular-nums;
	}

	.history .sync-badge {
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.03em;
		text-transform: uppercase;
		color: #f59e0b;
		background: rgba(245, 158, 11, 0.14);
		border: 1px solid rgba(245, 158, 11, 0.35);
		padding: 2px 6px;
		border-radius: 999px;
	}

	.history .type {
		font-weight: 600;
		min-width: 60px;
	}

	.history .value {
		color: var(--color-text);
		min-width: 50px;
	}

	.history .notes {
		color: var(--color-text-muted);
		font-style: italic;
		flex: 1;
		min-width: 60px;
	}

	.history .notes.empty {
		opacity: 0.4;
	}

	.history .notes-note {
		color: var(--color-text);
		font-style: normal;
		flex: 1;
		min-width: 60px;
	}

	.history .actions {
		position: absolute;
		right: 0;
		top: 50%;
		display: flex;
		align-items: center;
		justify-content: flex-end;
		width: 44px;
		transform: translateY(-50%);
	}

	.pending-text {
		font-size: 0.75rem;
		color: #f59e0b;
		white-space: nowrap;
	}

	.delete-btn {
		background: none;
		border: none;
		color: #f87171;
		font-size: 1.25rem;
		cursor: pointer;
		width: 44px;
		height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius);
		padding: 0;
		line-height: 1;
	}

	.delete-btn:hover {
		background: rgba(248, 113, 113, 0.15);
	}

	.delete-modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 1000;
		display: grid;
		place-items: center;
		padding: var(--spacing-lg);
		background: rgba(0, 0, 0, 0.5);
	}

	.delete-modal {
		width: min(100%, 320px);
		padding: var(--spacing-lg);
		border-radius: var(--radius);
		background: var(--color-surface);
		box-shadow: var(--shadow-xl);
	}

	.delete-modal h3 {
		margin: 0 0 var(--spacing-sm);
		font-size: 1.1rem;
	}

	.delete-modal p {
		margin: 0;
		color: var(--color-text-muted);
	}

	.delete-modal-actions {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--spacing-sm);
		margin-top: var(--spacing-lg);
	}

	.delete-modal-actions button {
		min-height: 44px;
		font-weight: 600;
	}

	.delete-modal-cancel {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		color: var(--color-text);
	}

	.delete-modal-confirm {
		background: var(--color-danger);
		color: var(--color-primary-contrast);
	}
</style>
