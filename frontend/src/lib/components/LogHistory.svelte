<script lang="ts">
	import { deleteLog, fetchLogsRange, type LogEntry } from '$lib/api/log';

	let {
		refreshTrigger = 0,
		windowStart,
		windowEnd,
		highlightedTimestamp,
		onHighlight
	}: {
		refreshTrigger?: number;
		windowStart: Date;
		windowEnd: Date;
		highlightedTimestamp: string | null;
		onHighlight: (ts: string | null) => void;
	} = $props();

	let logs = $state<LogEntry[]>([]);
	let confirmId = $state<number | null>(null);

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
			confirmId = null;
		}
	}

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

	function formatEntry(log: {
		entry_type: string;
		value: number;
		unit: string;
		created_by: string | null;
	}): string {
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

	function formatDateTime(ts: string): string {
		const d = new Date(ts);
		return d.toLocaleString('de-DE', {
			day: '2-digit',
			month: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
</script>

{#if logs.length > 0}
	<div class="history">
		<h3>Logbuch</h3>
		<ul>
			{#each logs as log}
				<li
					class:active={highlightedTimestamp === log.created_at}
					onmouseenter={() => onHighlight(log.created_at)}
					onmouseleave={() => onHighlight(null)}
					onclick={() =>
						onHighlight(highlightedTimestamp === log.created_at ? null : log.created_at)}
				>
					<span class="icon">{typeIcon(log.entry_type)}</span>
					<span class="date">{formatDateTime(log.created_at)}</span>
					{#if log.entry_type === 'note' || log.entry_type === 'alarm' || log.entry_type === 'success'}
						<span class="notes-note">{log.notes ?? ''}</span>
					{:else}
						<span class="value">{formatEntry(log)}</span>
						{#if log.notes}
							<span class="notes">— {log.notes}</span>
						{/if}
					{/if}
					<span class="actions">
						{#if confirmId === log.id}
							<span class="confirm">
								<span class="confirm-text">Löschen?</span>
								<button class="confirm-yes" onclick={() => remove(log.id)}>Ja</button>
								<button class="confirm-no" onclick={() => (confirmId = null)}>Nein</button>
							</span>
						{:else}
							<button class="delete-btn" onclick={() => (confirmId = log.id)} title="Löschen"
								>×</button
							>
						{/if}
					</span>
				</li>
			{/each}
		</ul>
	</div>
{/if}

<style>
	.history {
		background: var(--color-surface);
		padding: var(--spacing-md);
		border-radius: var(--radius);
		max-height: 400px;
		overflow-y: auto;
	}

	.history h3 {
		font-size: 0.9rem;
		margin: 0 0 var(--spacing-sm);
		color: var(--color-text-muted);
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
		display: flex;
		gap: var(--spacing-sm);
		align-items: center;
		font-size: 0.85rem;
		padding: var(--spacing-xs) 0;
		border-bottom: 1px solid var(--color-border);
		cursor: pointer;
	}

	.history li:hover {
		background: rgba(15, 118, 110, 0.05);
	}

	.history li.active {
		background: rgba(15, 118, 110, 0.1);
		border-left: 3px solid #0f766e;
		padding-left: 4px;
	}

	.history .icon {
		font-size: 1.1rem;
		min-width: 24px;
		text-align: center;
	}

	.history .date {
		color: var(--color-text-muted);
		min-width: 100px;
		font-variant-numeric: tabular-nums;
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
		margin-left: auto;
		display: flex;
		align-items: center;
	}

	.delete-btn {
		background: none;
		border: none;
		color: #f87171;
		font-size: 1rem;
		cursor: pointer;
		width: 22px;
		height: 22px;
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

	.confirm {
		display: flex;
		gap: var(--spacing-xs);
		align-items: center;
	}

	.confirm-text {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		margin-right: 2px;
	}

	.confirm-yes,
	.confirm-no {
		padding: 2px 8px;
		font-size: 0.75rem;
		border-radius: var(--radius);
		border: none;
		cursor: pointer;
		font-weight: 600;
	}

	.confirm-yes {
		background: #ef4444;
		color: white;
	}

	.confirm-no {
		background: var(--color-bg);
		color: var(--color-text-muted);
		border: 1px solid var(--color-border);
	}

	.confirm-yes:hover {
		background: #dc2626;
	}

	.confirm-no:hover {
		background: var(--color-surface);
		color: var(--color-text);
	}
</style>
