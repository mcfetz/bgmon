export const DASHBOARD_SECTION_TILES = ['graph', 'logbook'] as const;
export const DASHBOARD_STAT_TILES = [
	'daily-score',
	'prediction',
	'tir',
	'streak',
	'min-mean-max',
	'badges',
	'gmi',
	'readings'
] as const;
export const DASHBOARD_TILES = [...DASHBOARD_SECTION_TILES, ...DASHBOARD_STAT_TILES] as const;

export type DashboardTile = (typeof DASHBOARD_TILES)[number];
export type DashboardStatTile = (typeof DASHBOARD_STAT_TILES)[number];

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

const STORAGE_KEY_PREFIX = 'bgmon_dashboard_tiles_v1';

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null;
}

export function isDashboardTile(value: unknown): value is DashboardTile {
	return typeof value === 'string' && DASHBOARD_TILES.some((tile) => tile === value);
}

export function isDashboardStatTile(value: unknown): value is DashboardStatTile {
	return typeof value === 'string' && DASHBOARD_STAT_TILES.some((tile) => tile === value);
}

export function defaultDashboardTiles(): DashboardTile[] {
	return [...DASHBOARD_TILES];
}

export function parseDashboardTiles(value: unknown): DashboardTile[] | null {
	if (value === null) return null;
	if (!Array.isArray(value) || !value.every((tile) => isDashboardTile(tile) || tile === 'stats')) {
		return null;
	}

	const tiles = expandLegacyStats(value);
	return new Set(tiles).size === tiles.length ? tiles : null;
}

export function expandLegacyStats(tiles: readonly (DashboardTile | 'stats')[]): DashboardTile[] {
	return tiles.flatMap((tile) => (tile === 'stats' ? DASHBOARD_STAT_TILES : [tile]));
}

export function dashboardTilesStorageKey(authToken: string | null): string {
	const tokenSuffix = authToken?.slice(-12) ?? 'anonymous';
	return `${STORAGE_KEY_PREFIX}:${tokenSuffix}`;
}

export function loadDashboardTiles(storage: StorageLike, authToken: string | null): DashboardTile[] {
	const rawValue = storage.getItem(dashboardTilesStorageKey(authToken));
	if (!rawValue) return defaultDashboardTiles();

	try {
		return parseDashboardTiles(JSON.parse(rawValue)) ?? defaultDashboardTiles();
	} catch (error) {
		console.warn('Dashboard-Kacheln konnten nicht aus dem lokalen Speicher geladen werden.', error);
		return defaultDashboardTiles();
	}
}

export function saveDashboardTiles(
	storage: StorageLike,
	authToken: string | null,
	tiles: readonly DashboardTile[]
): void {
	storage.setItem(dashboardTilesStorageKey(authToken), JSON.stringify(tiles));
}

export function toggleDashboardTile(
	tiles: readonly DashboardTile[],
	tile: DashboardTile
): DashboardTile[] {
	return tiles.includes(tile) ? tiles.filter((candidate) => candidate !== tile) : [...tiles, tile];
}

export function hasDashboardTile(tiles: readonly DashboardTile[], tile: DashboardTile): boolean {
	return tiles.includes(tile);
}

export function shouldShowTimeControls(
	isEditMode: boolean,
	tiles: readonly DashboardTile[]
): boolean {
	return isEditMode || hasDashboardTile(tiles, 'graph') || hasDashboardTile(tiles, 'logbook');
}

export function visibleDashboardStatTiles(
	tiles: readonly DashboardTile[]
): DashboardStatTile[] {
	return DASHBOARD_STAT_TILES.filter((tile) => hasDashboardTile(tiles, tile));
}

export function dashboardTilesFromPreferences(value: unknown): DashboardTile[] | null {
	if (!isRecord(value) || !('dashboard_tiles' in value)) return null;
	return parseDashboardTiles(value.dashboard_tiles);
}
