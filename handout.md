# bgmon — Blutzucker-Monitor für die ganze Familie

## Was ist bgmon?

bgmon zeigt dir jederzeit den aktuellen Blutzuckerwert deines Kindes an — live, auf dem Handy, Tablet oder Computer. Du kannst Kohlenhydrate (KE) und Insulin eintragen, wirst bei gefährlichen Werten alarmiert und bekommst sogar eine Vorhersage, wohin sich der Blutzucker entwickelt.

Die App ist eine **PWA** (Progressive Web App): Du kannst sie auf deinem Homescreen installieren wie eine normale App. Sie funktioniert auch ohne Internetzugang (die letzten Werte bleiben sichtbar).

---

## Erste Schritte

### Anmelden

1. Öffne die App-URL im Browser (z. B. `https://bgmon.familie-heise.de`)
2. Melde dich mit deiner E-Mail und deinem Passwort an
3. Du bleibst eingeloggt — auch nach Schließen des Browsers

### Auf dem Homescreen installieren (empfohlen)

- **iPhone/iPad:** In Safari auf das Teilen-Symbol tippen → „Zum Home-Bildschirm"
- **Android:** Im Chrome-Menü → „App installieren" oder „Zum Startbildschirm hinzufügen"
- **Desktop:** In der Browser-Adressleiste rechts auf das Installations-Symbol klicken

---

## Das Dashboard

Das Dashboard ist deine Startseite. Es zeigt:

| Bereich | Was du siehst |
|---|---|
| **Großer BG-Wert** | Der aktuelle Blutzucker in mg/dL. Farbig: Grün = im Zielbereich (70–180), Gelb = grenzwertig, Rot = kritisch |
| **Trendpfeil** | Zeigt an, ob der Blutzucker steigt (↑), fällt (↓) oder stabil ist (→) |
| **Verlaufsgraph** | Die letzten Stunden als Kurve. Du kannst mit den Buttons (`-1h`, `-6h`, `-12h`, `-1t`, `-1w`) rein- und rauszoomen oder mit `Jetzt` zur aktuellen Zeit springen |
| **Stats-Kacheln** | Siehe unten |

### Stats-Kacheln

- **Heute ⭐** — Deine Tagespunkte und dein Level. Tippen für Details
- **Prognose +30min** — Der vorhergesagte Blutzucker in 30 Minuten. Tippen für alle Zeithorizonte (30/60/120 min) mit Genauigkeit
- **Time in Range** — Wie viel Prozent der Zeit der Blutzucker im Zielbereich (70–180 mg/dL) lag. Der farbige Balken zeigt an: Rot = zu niedrig, Grün = im Bereich, Orange = zu hoch
- **Streak 🏆** — Wie lange der Blutzucker schon ununterbrochen im Zielbereich liegt. Tippen für Details
- **Min / Ø / Max** — Der niedrigste, durchschnittliche und höchste Wert der letzten Stunde
- **Badges 🏅** — Freigeschaltete Erfolge. Tippen für die Sammlung
- **GMI (eA1c)** — Geschätzter Langzeitblutzuckerwert (wie der HbA1c beim Arzt)
- **Messwerte** — Anzahl der Messungen in der aktuellen Ansicht

### Großer BG-Bildschirm

Tippe auf den aktuellen Blutzuckerwert, um eine vergrößerte Ansicht zu öffnen — ideal für nachts oder aus der Entfernung. Dort siehst du auch die Prognose für die nächsten 30/60/120 Minuten.

---

## Eintragungen (Logbuch)

Das Logbuch erfasst, was du deinem Kind gibst:

### Kohlenhydrate (KE)
1 KE = 10 g Kohlenhydrate. Gib einfach die Anzahl der KE ein, z. B. `5` für 50 g.

### Insulin
Gib die Insulineinheiten ein. Das System errechnet automatisch einen Vorschlag basierend auf:
- Deiner KE-Eingabe × KE-Faktor
- + Korrekturwert anhand des aktuellen Blutzuckers

### Basal (Basalrate)
Das Basalinsulin wird nur einmal pro Tag eingetragen. Das System zeigt den letzten Wert an.

### Notizen
Freitext für besondere Vorkommnisse („Sport gemacht", „krank", etc.)

### Simulationsvorschau
Sobald du KE oder Insulin eintippst, erscheint eine **gestrichelte Linie im Graph** — das ist die Simulation, wie sich der Blutzucker mit dieser Eingabe entwickeln könnte. Noch nicht gespeichert — du siehst die Auswirkung vor dem Abschicken.

---

## Alarme

bgmon überwacht den Blutzucker automatisch und alarmiert dich, wenn Werte gefährlich werden.

### Schwellwerte

| Stufe | Standard | Bedeutung |
|---|---|---|
| Kritisch niedrig | < 54 mg/dL | Sofort handeln! |
| Niedrig | < 70 mg/dL | Bald Kohlenhydrate geben |
| Hoch | > 180 mg/dL | Bald korrigieren |
| Kritisch hoch | > 250 mg/dL | Sofort handeln! |

### So wirst du alarmiert

- **Push-Benachrichtigung** auf deinem Handy (auch wenn der Browser geschlossen ist)
- **Telefonanruf** (Twilio) mit gesprochener Ansage des aktuellen Werts (wenn konfiguriert)
- Nach einem Alarm wird für 15 Minuten **stummgeschaltet** (Snooze), damit keine Alarm-Flut entsteht

### Notification-Profile

Du kannst für verschiedene Tageszeiten unterschiedliche Profile anlegen (z. B. „Nachts nur Anruf", „Tagsüber Push + Anruf"). Jedes Profil wird einem Schwellwert zugeordnet.

---

## Nachtmodus

Wenn du eine **Nachtschicht** startest, wechselt die App in ein augenschonendes Design mit reduzierter Helligkeit. Der große BG-Bildschirm zeigt den aktuellen Wert in maximaler Größe.

---

## Familie-Dashboard

Du kannst einen **öffentlichen Link** erstellen, den du mit anderen teilst (z. B. Großeltern, Betreuer). Der Link zeigt den aktuellen Blutzuckerwert ohne Login — nur lesen, keine Eingaben möglich.

---

## Schicht-Management

Wenn mehrere Personen die Betreuung übernehmen, können Schichten geplant und dokumentiert werden. So weiß jeder, wer gerade zuständig ist.

---

## Einstellungen

In den Einstellungen (erreichbar über das Zahnrad-Icon oben rechts) kannst du:

- **Schwellwerte** ändern (pro Benutzer)
- **KE-Faktor** und **Korrekturfaktor** anpassen
- **Benutzer verwalten** (Admin)
- **Notification-Profile** erstellen
- **Snooze anpassen** / aufheben
- **Twilio-Nummern** verwalten
- **BG-Prognose trainieren** (ML-Modell neu trainieren)
- **Historische LibreLinkUp-Daten** laden

---

## BG-Prognose (ML)

Die App kann den Blutzucker für die nächsten 30, 60 und 120 Minuten vorhersagen. Die Prognose basiert auf:

- Dem aktuellen Blutzuckerwert und -verlauf
- Eingegebenen Kohlenhydraten und Insulin
- Der Tageszeit

**Wichtig:** Die Prognose ist eine **statistische Schätzung** und ersetzt keine medizinische Beratung. Die Genauigkeit (MAE) wird dir im Prognose-Modal angezeigt. Sie verbessert sich mit mehr Trainingsdaten.

---

## Tipps für den Alltag

1. **Trage jede Mahlzeit ein** — nur so kann die Prognose und die TIR-Statistik korrekt arbeiten
2. **Installiere die App auf dem Homescreen** — dann bekommst du Push-Benachrichtigungen auch bei geschlossenem Browser
3. **Nutze die Simulationsvorschau** — so siehst du vor dem Spritzen, wie sich Insulin und KE auf den Verlauf auswirken
4. **Schau regelmäßig ins Logbuch** — hier siehst du alle vergangenen Einträge
5. **Bei Problemen:** Schau in den Einstellungen unter „Hilfe" (diesen Text findest du auch dort)
