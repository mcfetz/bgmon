export interface WhatsNewEntry {
	readonly id: string;
	readonly versionPrefixes: readonly string[];
	readonly publishedAt: string;
	readonly title: string;
	readonly highlights: readonly string[];
}

export const WHATS_NEW_ENTRIES: readonly WhatsNewEntry[] = [
	{
		id: '2026-07-17-personal-dashboard-mobile-logbook',
		versionPrefixes: [],
		publishedAt: '2026-07-17',
		title: 'Persönliches Dashboard und besseres Logbuch auf dem Handy',
		highlights: [
			'Das Dashboard lässt sich jetzt persönlich zusammenstellen: Diagramm, Logbuch und jede einzelne Statistik-Kachel können ein- oder ausgeblendet werden.',
			'Über den Stift am unteren Rand wechselst du in den Bearbeitungsmodus und speicherst deine Auswahl mit dem Haken.',
			'Der Plus-Button für neue Einträge schwebt jetzt fest und gut erreichbar am unteren Bildschirmrand.',
			'Die Zeitbereichsauswahl ist auf kleinen Bildschirmen jetzt kompakt und direkt erreichbar.',
			'Das Logbuch zeigt Einträge übersichtlicher: pro Zeile steht nur noch die Uhrzeit, neue Tage erhalten eine eigene Überschrift und die Liste lässt sich ein- oder ausklappen.',
			'Zum Löschen eines Eintrags erscheint jetzt eine klare Bestätigung statt einer engen Auswahl direkt in der Zeile.',
			'In den Einstellungen sind die Bereiche jetzt nach Persönliches, Diabetes, Infos und Admin sortiert.'
		]
	},
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
