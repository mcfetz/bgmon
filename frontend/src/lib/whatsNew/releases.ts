export interface WhatsNewEntry {
	readonly id: string;
	readonly versionPrefixes: readonly string[];
	readonly publishedAt: string;
	readonly title: string;
	readonly highlights: readonly string[];
}

export const WHATS_NEW_ENTRIES: readonly WhatsNewEntry[] = [
	{
		id: '2026-08-26-agp-report',
		versionPrefixes: ['15954c3'],
		publishedAt: '2026-08-26',
		title: 'AGP-Bericht: Glukosemuster übersichtlich zusammengefasst',
		highlights: [
			'📄 Neuer AGP-Bericht: In den Diabetes-Einstellungen kannst du jetzt einen Bericht für einen frei wählbaren Zeitraum erstellen.',
			'📊 Durchschnitt, Zeit im Zielbereich, GMI, Variabilität und Datenabdeckung werden kompakt dargestellt.',
			'🕒 AGP-Kurve, tägliche Profile, Monats- und Wochenübersichten zeigen den Verlauf nach Tageszeit und Datum.',
			'📝 Protokollierte Kohlenhydrate, Schnellinsulin, Basalinsulin und niedrige Ereignisse erscheinen direkt im Bericht.',
			'🖨️ Mit „Drucken / PDF“ erhältst du eine A4-Druckansicht; auf dem Handy bleiben breite Diagramme separat scrollbar.'
		]
	},
	{
		id: '2026-08-24-no-data-alarm',
		versionPrefixes: ['4733a82'],
		publishedAt: '2026-08-24',
		title: 'Keine-Daten-Alarm: Werdet informiert, wenn der Sensor nicht mehr liefert',
		highlights: [
			'📡 Alarm bei Datenausfall: Wenn keine Blutzuckerwerte mehr einlaufen, wird jetzt zuverlässig alarmiert — nicht nur bei hohen oder tiefen Werten.',
			'⏱ Einstellbarer Schwellwert: In den Einstellungen → Schwellwerte legst du fest, nach wie vielen Minuten ohne Werte der Alarm auslöst (Standard: 15).',
			'🔔 Individuell im Profil: In deinem Benachrichtigungs-Profil wählst du wie gewohnt, was passieren soll — Push, Anruf oder nichts.',
			'📝 Wie bei allen Alarms: Eintrag ins Logbuch und Snooze inklusive. Sobald wieder frische Werte da sind, wird der Alarm automatisch beendet.'
		]
	},
	{
		id: '2026-07-28-smart-alerts',
		versionPrefixes: ['4ad1763', 'c9e99ff', '93f9daf'],
		publishedAt: '2026-07-28',
		title: 'Smart Alerts: Mustererkennung & Handlungsempfehlungen',
		highlights: [
			'🚀 Postprandialer Spike: Erkennt starke Blutzucker-Anstiege nach dem Essen und empfiehlt Spritz-Ess-Abstand.',
			'🔄 Hypo-Rebound: Warnt vor Gegenregulation nach Unterzuckerungen — kein unnötiges Korrektur-Insulin spritzen!',
			'💉 Insulin-Stacking: Warnt vor mehrfachen Korrektur-Gaben innerhalb der Insulin-Wirkdauer inkl. IOB-Berechnung.',
			'🌅 Dawn-Phänomen: Erkennt morgendliche Blutzucker-Anstiege ohne Essen (04:00–08:00).',
			'🎢 Überkorrektur-Kreislauf: Erkennt den gefährlichen Hypo→Hyper→Hypo-Zyklus.',
			'⚠️ Alle Warnungen erscheinen als einheitliche Badges unter dem Header und im großen BG-Modal.',
			'📝 Jeder Alert wird automatisch im Logbuch dokumentiert für die Diabetes-Besprechung.'
		]
	},
	{
		id: '2026-07-27-compression-low-sampling',
		versionPrefixes: ['fc0a538', '4435082', '0b0b1db', '8f690c8', '762e553'],
		publishedAt: '2026-07-27',
		title: 'Kompressionstiefwert-Erkennung & schnellere Diagramme',
		highlights: [
			'📱 Kein ungewolltes Zoomen mehr: Pinch-to-Zoom auf dem Handy ist jetzt deaktiviert — das Dashboard bleibt immer in der richtigen Größe.',
			'🕐 Nachteinträge korrigiert: Einträge zwischen 0 und 2 Uhr nachts wurden vorher mit einem falschen Datum gespeichert und waren morgens verschwunden.',
			'⚠️ Kompressionstiefwert-Warnung: Erkennt automatisch falsch-niedrige Werte durch Sensor-Kompression (z.\u00a0B. beim Liegen auf dem Sensor) und zeigt ein Warn-Badge am Glukosewert.',
			'🔔 Kompressionstiefwert-Hinweis in Push- und Voice-Benachrichtigungen — so weißt du, dass der Wert möglicherweise nicht stimmt.',
			'⚡ Schnellere Diagramme: Bei großen Zeitbereichen (ab 6 Stunden) lädt der Graph jetzt blitzschnell, weil die Daten automatisch reduziert werden.',
			'📋 Logbuch zeigt jetzt alle Einträge im gewählten Zeitraum — keine Begrenzung mehr auf die 100 neuesten.',
			'📈 Vorhersage-Zeile bleibt jetzt immer sichtbar (kein Springen mehr auf dem Handy).',
			'💊 KE-Faktor und Korrekturfaktor unterstützen jetzt Komma-Eingabe (1,3 statt 1.3).'
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
	},
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

	const currentIndex = WHATS_NEW_ENTRIES.findIndex((entry) =>
		matchesWhatsNewVersion(entry, appVersion)
	);
	return currentIndex === -1 ? WHATS_NEW_ENTRIES : WHATS_NEW_ENTRIES.slice(currentIndex);
}
