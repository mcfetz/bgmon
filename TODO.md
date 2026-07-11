# bgmon — TODO

## Offen / In Arbeit

### 1. Notification-Profile komplett testen
- [x] Profil im Header-Dropdown auswählen → wird in DB gespeichert
- [ ] BG > 180 → Alarm-Evaluator triggert Twilio-Call
- [ ] Logbuch zeigt Benachrichtigung
- [ ] Snooze (15 min) verhindert Folge-Alarme
- [ ] Snooze-Counter im Header sichtbar (FEHLT NOCH)

### 2. UI: SnoozeIndicator im Header
- [ ] Komponente erstellen die den Snooze-Status anzeigt
- [ ] Polling oder WebSocket für Live-Updates
- [ ] Anzeige: "Stumm bis HH:MM" wenn aktiv

### 3. Push-Benachrichtigungen implementieren
- [x] `dispatch_via_profile` für `push` area ist implementiert (`_dispatch_push`)
- [ ] Web Push Service (`web_push.py`) testen
- [ ] User-Subscription-Management

### 4. Security / Production-Hardening
- [ ] Webhook-Auth / Public-Webhook-Design in `notifications.py` separat neu aufsetzen
- [ ] Rate-Limit-Storage für Production auf Shared-Backend umstellen (statt `memory://`)
- [ ] Proxy-/Client-IP-Handling für `get_remote_address` vor Production prüfen
- [ ] Migration-Downgrades auf Datenverlust prüfen

### 5. Code-Qualität
- [ ] Pre-existing Test-Typing/LSP-Rauschen in `backend/tests/conftest.py` bereinigen
- [ ] `redundant-cast` Warning in `backend/bgmon_api/app.py` bereinigen
- [ ] Debug-Code aus alarm_evaluator.py entfernen
- [ ] Doppelte Funktionsdefinitionen VERMEIDEN (bereits 1x passiert!)

## Erledigt (diese Session)

### Backend
- [x] PostgreSQL als Primary Storage für Glucose-Readings
- [x] InfluxDB nur noch als Legacy-Passthrough
- [x] Libre-Fetcher Timestamp-Parsing Fix (US-Format)
- [x] Log-Entry 404 Bug Fix (trailing slash)
- [x] Backend-Endpoint `/api/settings/thresholds` für user-spezifische Schwellwerte
- [x] Backend-Endpoint `/api/settings/global` für globale Settings
- [x] Notification-Profile API (CRUD)
- [x] User-Active-Profile + Snooze API
- [x] Twilio Integration: From-Number, Test-Call
- [x] Alarm-Notification-Logik via Active Profile
- [x] `place_call(user, sgv, title)` mit BG-Wert in TwiML
- [x] `extensions.py` für saubere `db`/`migrate` Imports
- [x] Alarm-Logs im Logbuch (Benachrichtigung an X via Y)
- [x] Flask-Limiter zentral in `extensions.py` + `app.py` init
- [x] Login-Rate-Limit auf `POST /api/auth/login` (`10/min`, `30/hour`)
- [x] Login-Rate-Limit-Tests gehärtet inkl. Limiter-Reset pro Test
- [x] Logout gibt 500 zurück, wenn Session-Revocation in der DB fehlschlägt
- [x] Login-/Logout-DB-Fehler werden serverseitig geloggt
- [x] Leader-Check wieder aktiv für Alarm/Profile/Streak-Jobs

### Frontend
- [x] snipsel-ähnliches Layout (pill-shaped header, glass effect)
- [x] Inter-Font, Light/Dark-Mode Design-System
- [x] BG-Wert mit Trendpfeil, "vor X sec/min/h" Anzeige
- [x] ProfileSelector im Header (Icon + Modal mit Klarnamen)
- [x] Icon-Editor im Profile-Editor (frei wählbar + Quick-Picks)
- [x] Settings-Dialog: Konto, Schwellwerte, Behandlung, Twilio, Benachrichtigungen
- [x] Testanruf-Button im Twilio-Tab
- [x] "Stumm" aus Bereichen entfernt (durch "— Nicht aktiv —" ersetzt)
- [x] Logbuch-Refresh nach Speichern eines Eintrags
- [x] Graph-Refresh nach Speichern (loadDashboard nach onSaved)
- [x] ±0.5 Buttons für Insulin/Basal
- [x] Modal-Overflow Fix (backdrop-filter entfernt)

### Migrationen
- [x] `20260628_201007` — glucose_readings Tabelle
- [x] `02e0084e3298` — merge_heads
- [x] `20260629_240000` — twilio_from_number Spalte
- [x] `20260629_250000` — notification_profiles + notification_assignments
- [x] `20260629_260000` — icon Spalte in notification_profiles
- [x] `20260629_270000` — notification_area enum auf UPPERCASE gefixt
- [x] `20260629_280000` — notification_threshold enum auf UPPERCASE gefixt
- [x] `20260629_290000` — user_active_profiles + user_snoozes

## Wichtige Notizen

### Circular Import
- `extensions.py` hat nur `db` und `migrate`
- `models.py` importiert `db` von `extensions` (lazy via `__getattr__`)
- `alarm_evaluator.py` macht **lazy imports** INNERHALB der Funktionen
- `auth_utils.py` macht **lazy imports** INNERHALB der Funktionen

### Doppelte Definitionen
- IMMER `grep -n "def funcname"` vor dem Ändern einer Funktion!
- Die letzte Definition gewinnt → kann neue Logik komplett überschreiben

### ntfy
- Endpoint: `https://ntfy.familie-heise.de/opencode`
- Tags müssen Array sein, nicht String!

### Test-Anrufe
- `BGMON_TWILIO_NUMBERS` für vordefinierte Nummern
- `BGMON_TWILIO_FROM_NUMBER` als Fallback
- Test: `POST /api/settings/twilio/test`

### Active Profile
- `user_active_profiles` Tabelle (1:1 User → Profile)
- `PUT /api/notifications/active` zum Setzen
- `GET /api/notifications/active` zum Abrufen
- Frontend: `ProfileSelector.svelte` nutzt API statt localStorage

### Snooze
- `user_snoozes` Tabelle (1:1 User → Snooze)
- 15 min nach Alarm
- `POST /api/notifications/snooze` (manuell)
- Auto-Snooze nach `dispatch_via_profile`
- `is_active` Property prüft `snooze_until > now`
