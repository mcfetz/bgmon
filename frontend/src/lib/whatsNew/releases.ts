export interface WhatsNewEntry {
	readonly id: string;
	readonly versionPrefixes: readonly string[];
	readonly publishedAt: string;
	readonly title: string;
	readonly highlights: readonly string[];
}

export const WHATS_NEW_ENTRIES: readonly WhatsNewEntry[] = [
	{
		id: '2026-07-16-offline-logbook',
		versionPrefixes: ['5402517'],
		publishedAt: '2026-07-16',
		title: 'Offline-Logbuch, neue Farben und besseres Handling',
		highlights: [
			'Einträge für KE, Insulin, Basal und Notizen lassen sich jetzt auch ohne Internet speichern.',
			'Offline gespeicherte Einträge erscheinen sichtbar im Logbuch und werden später automatisch synchronisiert.',
			'Im Logbuch gibt es jetzt Filter nach Kategorien, damit die Ansicht schneller übersichtlich wird.',
			'Der Farbmodus lässt sich besser anpassen: Auto, Hell, Dunkel und eigene Farben für mehr Bereiche der App.',
			'Snooze reagiert verlässlicher und die eingestellte Snooze-Dauer wird persönlicher übernommen.'
		]
	}
];

export function matchesWhatsNewVersion(entry: WhatsNewEntry, appVersion: string): boolean {
	if (!appVersion) return false;

	return entry.versionPrefixes.some(
		(versionPrefix) => appVersion === versionPrefix || appVersion.startsWith(versionPrefix)
	);
}

export function getVisibleWhatsNewEntries(appVersion: string): readonly WhatsNewEntry[] {
	if (!appVersion) return WHATS_NEW_ENTRIES;

	const currentIndex = WHATS_NEW_ENTRIES.findIndex((entry) => matchesWhatsNewVersion(entry, appVersion));
	return currentIndex === -1 ? WHATS_NEW_ENTRIES : WHATS_NEW_ENTRIES.slice(currentIndex);
}
