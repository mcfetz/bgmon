import { describe, expect, it } from 'vitest';
import {
	dashboardTilesFromPreferences,
	dashboardTilesStorageKey,
	defaultDashboardTiles,
	expandLegacyStats,
	hasDashboardTile,
	isDashboardStatTile,
	loadDashboardTiles,
	shouldShowTimeControls,
	toggleDashboardTile,
	visibleDashboardStatTiles
} from './dashboardTiles';
import type { DashboardTile } from './dashboardTiles';

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

describe('dashboard tile preferences', () => {
	it('defaults to every tile when no local preference exists', () => {
		const storage = createMemoryStorage();

		expect(loadDashboardTiles(storage, 'session-token')).toEqual(defaultDashboardTiles());
	});

	it('loads a valid user-scoped local preference', () => {
		const key = dashboardTilesStorageKey('session-token');
		const storage = createMemoryStorage({ [key]: JSON.stringify(['graph', 'tir']) });

		expect(loadDashboardTiles(storage, 'session-token')).toEqual(['graph', 'tir']);
	});

	it('falls back to every tile for invalid local data', () => {
		const key = dashboardTilesStorageKey('session-token');
		const storage = createMemoryStorage({ [key]: JSON.stringify(['graph', 'unknown']) });

		expect(loadDashboardTiles(storage, 'session-token')).toEqual(defaultDashboardTiles());
	});

	it('toggles a tile without mutating the previous selection', () => {
		const before: DashboardTile[] = ['graph', 'logbook'];
		const after = toggleDashboardTile(before, 'graph');

		expect(before).toEqual(['graph', 'logbook']);
		expect(after).toEqual(['logbook']);
		expect(toggleDashboardTile(after, 'tir')).toEqual(['logbook', 'tir']);
	});

	it('shows time controls only for edit mode or time-aware active tiles', () => {
		expect(shouldShowTimeControls(false, ['tir'])).toBe(false);
		expect(shouldShowTimeControls(false, ['graph'])).toBe(true);
		expect(shouldShowTimeControls(false, ['logbook'])).toBe(true);
		expect(shouldShowTimeControls(true, [])).toBe(true);
	});

	it('expands the legacy statistics tile to every individual statistics card', () => {
		const expanded = expandLegacyStats(['graph', 'stats']);

		expect(expanded).toHaveLength(9);
		expect(visibleDashboardStatTiles(expanded)).toHaveLength(8);
		expect(isDashboardStatTile('daily-score')).toBe(true);
		expect(isDashboardStatTile('stats')).toBe(false);
	});

	it('accepts an explicit server preference and ignores malformed payloads', () => {
		expect(dashboardTilesFromPreferences({ dashboard_tiles: ['graph'] })).toEqual(['graph']);
		expect(dashboardTilesFromPreferences({ dashboard_tiles: null })).toBeNull();
		expect(dashboardTilesFromPreferences({ dashboard_tiles: ['graph', 'graph'] })).toBeNull();
		expect(hasDashboardTile(['tir'], 'tir')).toBe(true);
	});
});
