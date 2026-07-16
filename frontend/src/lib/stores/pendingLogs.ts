import { get, writable } from 'svelte/store';
import { getAuthToken } from '$lib/auth';
import { createLog, fetchLogsRange, type LogEntry, type LogEntryType } from '$lib/api/log';

export type PendingLogEntryType = Extract<LogEntryType, 'carbs' | 'insulin' | 'basal' | 'note'>;
export type PendingLogSyncState = 'pending' | 'syncing';

export type PendingLogInput = {
	readonly entry_type: PendingLogEntryType;
	readonly value: number;
	readonly unit: string;
	readonly notes: string | null;
	readonly created_at: string;
	readonly group_id: string;
	readonly sequence: number;
};

export interface PendingLogEntry extends LogEntry {
	readonly local_id: string;
	readonly group_id: string;
	readonly sequence: number;
	readonly queued_at: string;
	readonly sync_state: PendingLogSyncState;
	readonly attempts: number;
	readonly last_attempt_at: string | null;
}

const STORAGE_PREFIX = 'bgmon_pending_logs_v1';

const pendingLogEntriesStore = writable<readonly PendingLogEntry[]>([]);
let loadedStorageKey: string | null = null;

export const pendingLogEntries = {
	subscribe: pendingLogEntriesStore.subscribe
};

function getStorageKey(): string {
	const tokenSuffix = getAuthToken()?.slice(-12) ?? 'anon';
	return `${STORAGE_PREFIX}:${tokenSuffix}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null;
}

function isPendingLogEntryType(value: unknown): value is PendingLogEntryType {
	return value === 'carbs' || value === 'insulin' || value === 'basal' || value === 'note';
}

function isPendingLogSyncState(value: unknown): value is PendingLogSyncState {
	return value === 'pending' || value === 'syncing';
}

function isPendingLogEntry(value: unknown): value is PendingLogEntry {
	if (!isRecord(value)) return false;
	return (
		typeof value.id === 'number' &&
		typeof value.local_id === 'string' &&
		isPendingLogEntryType(value.entry_type) &&
		typeof value.value === 'number' &&
		typeof value.unit === 'string' &&
		(value.notes === null || typeof value.notes === 'string') &&
		typeof value.created_at === 'string' &&
		typeof value.group_id === 'string' &&
		typeof value.sequence === 'number' &&
		typeof value.queued_at === 'string' &&
		isPendingLogSyncState(value.sync_state) &&
		typeof value.attempts === 'number' &&
		(value.last_attempt_at === null || typeof value.last_attempt_at === 'string')
	);
}

function normalizeNotes(notes: string | null): string {
	return (notes ?? '').trim();
}

export function sortPendingLogEntries<T extends { readonly queued_at: string; readonly sequence: number }>(
	entries: readonly T[]
): T[] {
	return [...entries].sort((a, b) => {
		const queuedDiff = new Date(a.queued_at).getTime() - new Date(b.queued_at).getTime();
		if (queuedDiff !== 0) return queuedDiff;
		return a.sequence - b.sequence;
	});
}

export function sortLogsByCreatedAtDesc<T extends { readonly created_at: string }>(
	entries: readonly T[]
): T[] {
	return [...entries].sort(
		(a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
	);
}

function readPendingLogEntriesFromStorage(storageKey: string): readonly PendingLogEntry[] {
	if (typeof window === 'undefined') return [];
	const raw = window.localStorage.getItem(storageKey);
	if (!raw) return [];
	try {
		const parsed: unknown = JSON.parse(raw);
		if (!Array.isArray(parsed)) return [];
		return sortPendingLogEntries(parsed.filter(isPendingLogEntry));
	} catch (error) {
		if (error instanceof SyntaxError) {
			return [];
		}
		throw error;
	}
}

function writePendingLogEntriesToStorage(entries: readonly PendingLogEntry[]): void {
	if (typeof window === 'undefined') return;
	const storageKey = getStorageKey();
	loadedStorageKey = storageKey;
	if (entries.length === 0) {
		window.localStorage.removeItem(storageKey);
		return;
	}
	window.localStorage.setItem(storageKey, JSON.stringify(entries));
}

function replacePendingLogEntries(entries: readonly PendingLogEntry[]): void {
	const nextEntries = sortPendingLogEntries(entries);
	pendingLogEntriesStore.set(nextEntries);
	writePendingLogEntriesToStorage(nextEntries);
}

function generateGroupId(): string {
	return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
		? crypto.randomUUID()
		: `group-${Date.now()}`;
}

function generateLocalId(sequence: number): string {
	return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
		? crypto.randomUUID()
		: `local-${Date.now()}-${sequence}`;
}

function createSyntheticId(queuedAt: string, sequence: number): number {
	return -(new Date(queuedAt).getTime() * 100 + sequence + 1);
}

export function ensurePendingLogEntriesLoaded(): void {
	if (typeof window === 'undefined') return;
	const storageKey = getStorageKey();
	if (loadedStorageKey === storageKey) return;
	loadedStorageKey = storageKey;
	pendingLogEntriesStore.set(readPendingLogEntriesFromStorage(storageKey));
}

export function createPendingLogInputs(
	entries: readonly Omit<PendingLogInput, 'group_id' | 'sequence'>[]
): PendingLogInput[] {
	const groupId = generateGroupId();
	return entries.map((entry, index) => ({
		...entry,
		group_id: groupId,
		sequence: index
	}));
}

export function queuePendingLogEntries(
	entries: readonly PendingLogInput[]
): PendingLogEntry[] {
	ensurePendingLogEntriesLoaded();
	if (entries.length === 0) return [];
	const queuedAt = new Date().toISOString();
	const nextEntries = entries.map((entry) => ({
		id: createSyntheticId(queuedAt, entry.sequence),
		local_id: generateLocalId(entry.sequence),
		entry_type: entry.entry_type,
		value: entry.value,
		unit: entry.unit,
		notes: entry.notes,
		created_at: entry.created_at,
		created_by: null,
		group_id: entry.group_id,
		sequence: entry.sequence,
		queued_at: queuedAt,
		sync_state: 'pending' as const,
		attempts: 0,
		last_attempt_at: null
	}));
	replacePendingLogEntries([...get(pendingLogEntriesStore), ...nextEntries]);
	return nextEntries;
}

function updatePendingLogEntry(
	localId: string,
	updater: (entry: PendingLogEntry) => PendingLogEntry
): PendingLogEntry[] {
	const currentEntries = get(pendingLogEntriesStore);
	const nextEntries = currentEntries.map((entry) =>
		entry.local_id === localId ? updater(entry) : entry
	);
	replacePendingLogEntries(nextEntries);
	return nextEntries;
}

function removePendingLogEntry(localId: string): PendingLogEntry[] {
	const nextEntries = get(pendingLogEntriesStore).filter((entry) => entry.local_id !== localId);
	replacePendingLogEntries(nextEntries);
	return nextEntries;
}

export function hasMatchingServerLog(
	pendingEntry: Pick<PendingLogEntry, 'entry_type' | 'value' | 'unit' | 'notes' | 'created_at'>,
	serverLog: Pick<LogEntry, 'entry_type' | 'value' | 'unit' | 'notes' | 'created_at'>
): boolean {
	return (
		pendingEntry.entry_type === serverLog.entry_type &&
		pendingEntry.value === serverLog.value &&
		pendingEntry.unit === serverLog.unit &&
		normalizeNotes(pendingEntry.notes) === normalizeNotes(serverLog.notes) &&
		new Date(pendingEntry.created_at).getTime() === new Date(serverLog.created_at).getTime()
	);
}

async function findMatchingServerLog(entry: PendingLogEntry): Promise<LogEntry | null> {
	const centerTime = new Date(entry.created_at).getTime();
	const startIso = new Date(centerTime - 60_000).toISOString();
	const endIso = new Date(centerTime + 60_000).toISOString();
	const serverLogs = await fetchLogsRange(startIso, endIso);
	return serverLogs.find((serverLog) => hasMatchingServerLog(entry, serverLog)) ?? null;
}

export async function flushPendingLogEntries(): Promise<number> {
	ensurePendingLogEntriesLoaded();
	if (typeof navigator !== 'undefined' && !navigator.onLine) {
		return 0;
	}
	const pendingEntries = sortPendingLogEntries(get(pendingLogEntriesStore));
	let syncedCount = 0;

	for (const entry of pendingEntries) {
		updatePendingLogEntry(entry.local_id, (currentEntry) => ({
			...currentEntry,
			sync_state: 'syncing',
			attempts: currentEntry.attempts + 1,
			last_attempt_at: new Date().toISOString()
		}));

		try {
			const matchingServerLog = await findMatchingServerLog(entry);
			if (matchingServerLog) {
				removePendingLogEntry(entry.local_id);
				syncedCount++;
				continue;
			}

			const result = await createLog(
				entry.entry_type,
				entry.value,
				entry.unit,
				entry.notes ?? undefined,
				entry.created_at
			);
			if (result.entry) {
				removePendingLogEntry(entry.local_id);
				syncedCount++;
				continue;
			}

			updatePendingLogEntry(entry.local_id, (currentEntry) => ({
				...currentEntry,
				sync_state: 'pending'
			}));
			break;
		} catch (error) {
			if (error instanceof Error) {
				updatePendingLogEntry(entry.local_id, (currentEntry) => ({
					...currentEntry,
					sync_state: 'pending'
				}));
				break;
			}
			throw error;
		}
	}

	return syncedCount;
}
