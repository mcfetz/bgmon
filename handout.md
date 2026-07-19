# bgmon — Blutzucker-Monitor für die ganze Familie

## Was ist bgmon?

bgmon zeigt dir jederzeit den aktuellen Blutzuckerwert an — live, auf dem Handy, Tablet oder Computer. Du kannst Kohlenhydrate (KE) und Insulin eintragen, wirst bei gefährlichen Werten alarmiert und bekommst sogar eine Vorhersage, wohin sich der Blutzucker entwickelt.

Die App ist eine **PWA** (Progressive Web App): Du kannst sie auf deinem Homescreen installieren wie eine normale App. Sie funktioniert auch ohne Internetzugang (die letzten Werte bleiben sichtbar).

**Datenquelle:** Die Blutzuckerwerte kommen vom Libre-Sensor über die LibreLinkUp-API. bgmon holt die Daten **alle 60 Sekunden** ab. Ob die Verbindung zu Libre steht, siehst du an der Zeitangabe unter dem BG-Wert im Dashboard („vor X Min."). Solange hier unter 5 Minuten steht, kommen die Daten aktuell rein.

---

## Erste Schritte

### Auf dem Homescreen installieren (empfohlen)

- **iPhone/iPad:** In Safari auf das Teilen-Symbol tippen → „Zum Home-Bildschirm"
- **Android:** Im Chrome-Menü → „App installieren" oder „Zum Startbildschirm hinzufügen"
- **Desktop:** In der Browser-Adressleiste rechts auf das Installations-Symbol klicken

### Anmelden

1. Öffne die App-URL im Browser (z. B. `https://bgmon.familie-heise.de`)
2. Melde dich mit deiner E-Mail und deinem Passwort an
3. Du bleibst eingeloggt — auch nach Schließen des Browsers

---

## Das Dashboard

Das Dashboard ist deine Startseite.

### Aktueller BG-Wert

- Großer farbiger Wert in mg/dL: **Grün** = im Zielbereich (70–180), **Gelb** = grenzwertig, **Rot** = kritisch
- **Trendpfeil** darunter: ⇈/↑/↗ = steigend, ⇊/↓/↘ = fallend, → = stabil. Entspricht der Libre-Trendanzeige.
- **Delta** zum vorherigen Wert (z. B. "+5" oder "−3" mg/dL)
- **Zeitangabe** (z. B. „vor 2 Min.") — zeigt an, wie aktuell die Daten sind. Über 10 Minuten → Sensor-Verbindung prüfen!

### Verlaufsgraph

Die Blutzuckerkurve zeigt den Verlauf über den gewählten Zeitraum.

- **Zoom-Buttons** über dem Graph: `-1h`, `-6h`, `-12h`, `-1t` (Tag), `-1w` (Woche)
- **Jetzt-Button** springt zur aktuellen Zeit
- **Wischgeste (Swipe)** im Graph: horizontal nach links/rechts blättern
- Auf einen Punkt im Graph **tippen/hovern** zeigt den genauen Wert zu diesem Zeitpunkt

### Stats-Kacheln

- **Heute ⭐** — Tagespunkte und Level. Tippen öffnet Detailansicht mit Wochenübersicht
- **Prognose +30min** — Vorhergesagter Wert mit Konfidenzintervall (z. B. „142  (128–156) mg/dL"). Tippen öffnet Modal mit allen Horizonten + MAE (Genauigkeit)
- **Time in Range** — Prozentuale Zeit im Zielbereich. Farbbalken: Rot = zu niedrig, Grün = im Bereich, Orange = zu hoch. Tippen für Details
- **Streak 🏆** — Längste ununterbrochene Zeit im Zielbereich (in h:mm). Tippen für aktuellen + besten Streak
- **Min / Ø / Max** — Niedrigster, durchschnittlicher, höchster Wert
- **Badges 🏅** — Freigeschaltete Erfolge. Tippen für Sammlung
- **GMI (eA1c)** — Geschätzter Langzeitwert (vergleichbar mit HbA1c)
- **Messwerte** — Anzahl der Messungen in der aktuellen Ansicht

### Großer BG-Bildschirm

**Auf den großen BG-Wert tippen** öffnet eine Vollbild-Ansicht. Der Bildschirm bleibt mit **Wake Lock** dauerhaft an — ideal für nachts. Unten erscheinen die Prognose-Werte (+30/+60/+120).

---

## Eintragungen (Logbuch)

Das Logbuch findest du unter dem Dashboard. Vier Tabs: **KE**, **Insulin**, **Basal**, **Notiz**

### KE (Kohlenhydrate)
- 1 KE = 10 g Kohlenhydrate
- Nur **ganze Zahlen** (z. B. `5` für 50 g)
- Der KE-Wert wird für den Insulin-Vorschlag verwendet

### Insulin
- Einheiten in **0,5er-Schritten** (mit ± Buttons)
- **Automatischer Vorschlag:** Wird aus KE-Wert × KE-Faktor + Korrektur aus BG berechnet
- Zusätzlich kannst du einen **Korrekturwert** manuell eingeben
- Zeitpunkt einstellbar (Datum/Uhrzeit-Felder)

### Basal (Basalrate)
- Nur **einmal pro Tag** — der **letzte Wert** wird als Button angezeigt, drauftippen zum Übernehmen
- ± Buttons in 0,5er-Schritten

### Notiz
- Freitext für besondere Vorkommnisse („Sport", „krank", etc.)

### 🤖 KI-KE-Schätzung

Bei jeder Mahlzeit kannst du die KI fragen: **„Wie viele KE hat das?"** — per Text oder Foto.

- **Aus Notizen schätzen:** Schreibe ins Notizfeld, was gegessen wurde (z. B. „2 Scheiben Vollkornbrot mit Butter und Käse"), dann auf den 🤖-Button tippen. Die KI schätzt die KE und trägt sie ins KE-Feld ein.
- **Aus Foto schätzen:** Auf 📷 tippen, ein Foto von der Mahlzeit machen oder aus der Galerie wählen. Die KI erkennt die Lebensmittel, schätzt Portionen und berechnet die KE — alles automatisch.
- Die Schätzung erscheint in einem Popup mit der Zusammenfassung („1 Scheibe Vollkornbrot, 10g Butter, ...") und dem KE-Wert. Mit **✓ Übernehmen** wird der Wert ins KE-Feld gesetzt.
- Funktioniert im KE-Tab UND im Notizfeld der anderen Tabs (Insulin, Basal).

> ⚠️ Die KI-Schätzung ist ein **Hilfsmittel** — kein Ersatz für eigenes Abwiegen und Berechnen. Gerade bei Mischgerichten kann die Schätzung ungenau sein.

### Simulationsvorschau
Sobald du KE oder Insulin eintippst, erscheint nach ~0,5 Sek. eine **gestrichelte Linie im Graph**. Das ist die Vorschau, wie sich der BG mit dieser Eingabe entwickeln würde — **vor dem Speichern**.

### Einträge löschen
Im unteren Bereich (Logbuch-Verlauf) erscheinen alle gespeicherten Einträge. Jeder Eintrag hat einen **🗑️ Löschen-Button** mit Bestätigungsabfrage.

---

## Alarme

bgmon überwacht alle 30 Sekunden den Blutzucker und alarmiert bei Gefahr.

### Schwellwerte (Einstellungen → Schwellwerte)

| Stufe | Standard | Farbcode |
|---|---|---|
| Kritisch niedrig | < 54 mg/dL | 🔴 Rot |
| Niedrig | < 70 mg/dL | 🟡 Gelb |
| Hoch | > 180 mg/dL | 🟡 Gelb |
| Kritisch hoch | > 250 mg/dL | 🔴 Rot |

### Alarm-Arten

- **Push-Benachrichtigung** — Erscheint auf deinem Handy (auch bei geschlossenem Browser, wenn App installiert ist)
- **Telefonanruf (Twilio)** — Automatischer Anruf mit gesprochener Ansage: „Der aktuelle Blutzuckerwert beträgt X Milligramm pro Deziliter. [Titel]. Bitte überprüfen Sie den Blutzuckerwert des Patienten."
- **15-Minuten-Snooze** — Nach einem Alarm wird für 15 Minuten stummgeschaltet, um Alarm-Fluten zu vermeiden

### Push aktivieren

1. App auf dem **Homescreen installieren** (siehe oben)
2. Beim ersten Besuch fragt der Browser nach Push-Erlaubnis → **„Erlauben"** wählen
3. Unter **Einstellungen → Push** siehst du den aktuellen Status
4. Falls abgelehnt: In den Browser-Einstellungen manuell erlauben

### Notification-Profile

Unter **Einstellungen → Benachrichtigungen** kannst du verschiedene Profile anlegen:

- Jedes Profil hat einen **Namen** (z. B. „Tagsüber", „Nachts") und ein **Icon**
- Pro Profil legst du für jeden Schwellwert fest: **Push** und/oder **Anruf**
- Profile können per **Zeitplan** automatisch aktiviert werden (Nachtprofil)
- Das **aktive Profil** wird oben im Dashboard angezeigt

---

## Nachtprofil

Unter **Einstellungen → Benachrichtigungen** kannst du für jedes Notification-Profil eine Start- und Endzeit festlegen. Während der eingestellten Zeit wird dieses Profil automatisch aktiv — z. B. „nachts nur Anruf, kein Push".

---

## Schicht-Management

Wenn mehrere Personen betreuen: Schichten können im Dashboard **gestartet und beendet** werden. Sichtbar für alle, die eingeloggt sind.

---

## Familie-Dashboard (öffentlicher Link)

Für Großeltern, Betreuer oder andere Personen ohne eigenen Account:

1. In **Einstellungen → Benachrichtigungen** ein Profil auswählen
2. Das **Webhook-Token** ist gleichzeitig das Family-Token
3. Der Link lautet: `https://<deine-domain>/api/family/<token>`
4. Zeigt den **aktuellen BG-Wert ohne Login** — nur lesen, keine Eingaben

---

## BG-Prognose (ML)

Die App sagt den Blutzucker für **30, 60 und 120 Minuten** voraus. Eingabedaten:

- Aktueller BG-Wert und Verlauf (Durchschnitt, Steigung)
- Kohlenhydrate und Insulin der letzten 2–4 Stunden
- Tageszeit (sin/cos-Kodierung)

### Wo sichtbar:
- **Graph**: Gestrichelte farbige Linien für alle drei Horizonte (Blau=30 min, Lila=60 min, Orange=120 min) — sowohl als Live-Vorhersage als auch als **historische Linie** (wie gut hätte die Prognose vor 2 Stunden gepasst?)
- **Filter-Popup** (🔍-Icon rechts neben den Zoom-Buttons): Historische Prognosen für 30/60/120 min ein-/ausblenden
- **Prognose-Kachel**: Wert mit Konfidenzintervall (z. B. „142  (128–156) mg/dL")
- **Prognose-Modal**: Klick auf die Kachel → alle Horizonte + MAE + Disclaimer
- **BG-Modal**: Unten +30/+60/+120

### Genauigkeit (MAE)
MAE = „Mean Absolute Error" — die durchschnittliche Abweichung in mg/dL. Beispiel: MAE 46 bedeutet, der wahre Wert liegt im Schnitt ±46 mg/dL vom vorhergesagten entfernt. **Je mehr Trainingsdaten, desto genauer.**

> ⚠️ Die Prognose ist eine **statistische Schätzung** — kein Ersatz für medizinische Beratung.

---

## Einstellungen (⚙️)

Oben rechts im Dashboard erreichbar:

| Rubrik | Was du einstellen kannst |
|---|---|
| **Konto** 👤 | Name, E-Mail, Passwort ändern |
| **Behandlung** 💊 | KE-Faktor, Korrekturfaktor, Insulinwirkzeit |
| **Schwellwerte** 📊 | Alarmgrenzen (pro Benutzer) |
| **Benachrichtigungen** 🔕 | Profile, Push/Anruf, Nachtzeiten |
| **Push** 🔔 | Push-Status prüfen, neu abonnieren |
| **Twilio** 📞 | Telefonnummern, Testanruf |
| **Benutzer** 👥 | Benutzer verwalten (nur Admin) |
| **ML** 🧠 | Prognose-Modell trainieren + evaluieren. Nach jedem Training erscheint eine Notiz im Logbuch mit den Ergebnissen (MAE pro Horizont). |
| **Hilfe** ❓ | Diese Anleitung |

---

## Tipps für den Alltag

1. **App installieren** — Nur auf dem Homescreen bekommst du Push-Alarme bei geschlossenem Browser
2. **Jede Mahlzeit eintragen** — Damit Prognose, TIR und Insulin-Vorschlag korrekt arbeiten
3. **KI-KE-Schätzung nutzen** — 🤖 für Text, 📷 für Foto. Spart Zeit beim Abwiegen und Berechnen
4. **Simulationsvorschau nutzen** — Vor dem Spritzen die gestrichelte Linie im Graph prüfen
4. **Aktualität checken** — Unter dem BG-Wert steht „vor X Min.". >10 Minuten = Sensor prüfen
5. **Falsche Log-Einträge löschen** — Mit 🗑️ im Logbuch-Verlauf
6. **BG-Modal nachts** — Auf den Wert tippen, Bildschirm bleibt an
7. **Familie-Dashboard teilen** — Oma/Opa sehen den Wert ohne eigenes Login
