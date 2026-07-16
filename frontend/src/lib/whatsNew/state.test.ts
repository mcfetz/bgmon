import { describe, expect, it } from 'vitest';
import { getVisibleWhatsNewEntries } from './releases';
import { getSeenWhatsNewIds, getUnseenWhatsNewCount, markVisibleWhatsNewSeen } from './state';

type MemoryStorage = {
	readonly values: Map<string, string>;
	getItem: (key: string) => string | null;
	setItem: (key: string, value: string) => void;
};

function createMemoryStorage(initialEntries: Record<string, string> = {}): MemoryStorage {
	const values = new Map(Object.entries(initialEntries));

	return {
		values,
		getItem(key: string): string | null {
			return values.get(key) ?? null;
		},
		setItem(key: string, value: string): void {
			values.set(key, value);
		}
	};
}

describe('whats new helpers', () => {
	it('matches the current release by version prefix', () => {
		const entries = getVisibleWhatsNewEntries('54025176b58ce63769baf45e42d62402c12d9de2');
		expect(entries).toHaveLength(1);
		expect(entries[0]?.id).toBe('2026-07-16-offline-logbook');
	});

	it('returns all entries when the current version is unknown', () => {
		const entries = getVisibleWhatsNewEntries('unknown-build');
		expect(entries).toHaveLength(1);
	});

	it('tracks unseen entries until they are marked as seen', () => {
		const storage = createMemoryStorage();

		expect(getSeenWhatsNewIds(storage)).toEqual([]);
		expect(getUnseenWhatsNewCount('5402517', storage)).toBe(1);

		markVisibleWhatsNewSeen('5402517', storage);

		expect(getSeenWhatsNewIds(storage)).toEqual(['2026-07-16-offline-logbook']);
		expect(getUnseenWhatsNewCount('5402517', storage)).toBe(0);
	});

	it('ignores broken local storage payloads', () => {
		const storage = createMemoryStorage({
			bgmon_seen_whats_new_ids_v1: '{not-json}'
		});

		expect(getSeenWhatsNewIds(storage)).toEqual([]);
	});
});
