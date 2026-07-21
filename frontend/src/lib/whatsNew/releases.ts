export interface WhatsNewEntry {
	readonly id: string;
	readonly versionPrefixes: readonly string[];
	readonly publishedAt: string;
	readonly title: string;
	readonly highlights: readonly string[];
}

export const WHATS_NEW_ENTRIES: readonly WhatsNewEntry[] = [
	{
		id: '2026-07-18-ai-ke-ml-predictions',
		versionPrefixes: ['3dd5c81'],
		publishedAt: '2026-07-18',
		title: 'KI-gestützte KE-Schätzung & verbesserte Prognosen',
		highlights: [
			'🤖 KI-Schätzung im KE-Dialog: Notiztext analysieren lassen — die KI schätzt automatisch die Kohlenhydrateinheiten und liefert eine Begründung.',
			'📷 Foto-Upload: Mahlzeit abfotografieren — die KI erkennt die Lebensmittel, schätzt Mengen und berechnet die KE. Zusammenfassung landet automatisch im Notizfeld.',
			'📊 Drei Prognose-Linien im Diagramm: Blau (30 min), Lila (60 min) und Orange (120 min) zeigen, wohin sich der Blutzucker voraussichtlich entwickelt.',
			'🔍 Prognose-Filter: Über das Icon oben rechts im Diagramm lassen sich die einzelnen Prognose-Linien ein- und ausblenden.',
			'⚡ Automatische Prognose: Das ML-Modell rechnet jetzt alle 5 Minuten im Hintergrund, sodass die Prognosen immer aktuell sind.',
			'💉 Reine Korrektur-Insulin: Im Insulin-Tab kann jetzt eine reine Korrekturdosis ohne Mahlzeit-Insulin eingetragen werden.'
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
	},
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
		id: '2026-07-21-now-mode',
		versionPrefixes: ['2f3880b', '033dc37'],
		publishedAt: '2026-07-21',
		title: 'Now-Mode: Dashboard folgt automatisch der aktuellen Zeit',
		highlights: [
			'🔵 Now-Mode: Klick auf "Jetzt" aktiviert den Live-Modus — Diagramm und Logbuch bleiben automatisch auf dem aktuellen Zeitfenster.',
			'🟢 Der "Jetzt"-Button leuchtet farbig, solange der Now-Mode aktiv ist — so siehst du sofort, dass du live bist.',
			'⏪ Navigation beendet den Now-Mode: Sobald du im Diagramm nach vorne oder hinten blätterst, bleibt der Zeitbereich stehen.',
			'⏱ Standard-Zeitbereich jetzt 6 Stunden — für einen besseren Überblick über den aktuellen Tag.'
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
