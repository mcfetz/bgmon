import { browser } from '$app/environment';
import { getVisibleWhatsNewEntries } from './releases';

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

const SEEN_WHATS_NEW_KEY = 'bgmon_seen_whats_new_ids_v1';

function resolveStorage(storage?: StorageLike | null): StorageLike | null {
	if (storage !== undefined) return storage;
	if (!browser) return null;
	return window.localStorage;
}

function parseSeenIds(rawValue: string | null): string[] {
	if (!rawValue) return [];

	try {
		const parsed: unknown = JSON.parse(rawValue);
		if (!Array.isArray(parsed)) return [];
		return parsed.filter((value): value is string => typeof value === 'string');
	} catch {
		return [];
	}
}

export function getSeenWhatsNewIds(storage?: StorageLike | null): string[] {
	const resolvedStorage = resolveStorage(storage);
	if (!resolvedStorage) return [];
	return parseSeenIds(resolvedStorage.getItem(SEEN_WHATS_NEW_KEY));
}

export function getUnseenWhatsNewCount(appVersion: string, storage?: StorageLike | null): number {
	const seenIds = new Set(getSeenWhatsNewIds(storage));
	return getVisibleWhatsNewEntries(appVersion).filter((entry) => !seenIds.has(entry.id)).length;
}

export function markVisibleWhatsNewSeen(appVersion: string, storage?: StorageLike | null): void {
	const resolvedStorage = resolveStorage(storage);
	if (!resolvedStorage) return;

	const nextSeenIds = new Set(getSeenWhatsNewIds(resolvedStorage));
	for (const entry of getVisibleWhatsNewEntries(appVersion)) {
		nextSeenIds.add(entry.id);
	}

	resolvedStorage.setItem(SEEN_WHATS_NEW_KEY, JSON.stringify([...nextSeenIds]));
}
