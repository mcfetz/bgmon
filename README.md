# bgmon — Blutzucker-Monitoring-System

> Ein selbstgehostetes Echtzeit-Monitoring für kontinuierliche Glukosemessung (CGM) mit Alarmen, Push-Notifications, Telefonanrufen und Gamification für Patient & Pflegende.

![Dashboard](docs/screenshots/dashboard.png)
*Platzhalter — Screenshot des Dashboards folgt*

---

## Features

### Kern
- **Live-Dashboard** mit Verlaufsgraph (mg/dL / mmol/L), TIR-Stats und aktueller Glukosewert
- **CGM-Integration** via [LibreLinkUp](https://www.librelinkup.com/) — automatischer Polling im 30-Sekunden-Takt
- **Persistenz** in PostgreSQL (Schwellwerte, Logs, Alarme, Konfiguration)
- **InfluxDB** als optionaler sekundärer Storage für historische Auswertungen
- **Authentifizierung** mit Session-Cookies, bcrypt-gehashte Passwörter, Admin-Rollen

### Alarme
- **Vierstufige Schwellwerte** pro User: `critical_low` / `low` / `high` / `critical_high`
- **Twilio-Telefonanrufe** mit deutschem Sprachtext, automatischer Retry (konfigurierbar)
- **Web-Push** via VAPID — funktioniert auch wenn das PWA geschlossen ist
- **Snooze-System** (15 min) verhindert Alarm-Spam
- **Notification-Profile** mit eigenem Routing pro Schwellwert (Push vs. Anruf)

### Pflege & Übergabe
- **Schicht-Management** für Nachtdienste
- **Familie-Dashboard** mit eigenem Zugriffstoken (read-only, öffentlich teilbar)
- **Logbuch** für Kohlenhydrate, Insulin, Basal und Notizen
- **Nachtprofil** mit reduzierter UI-Helligkeit und vereinfachter Bedienung

### Gamification
- **Streak-Tracking** für konsequente Eintragungen
- **TIR-Statistik** (Time-in-Range) auf Wochen-/Monatsbasis

### KI-Integration
- **KE-Schätzung aus Text**: Beschreibe die Mahlzeit („2 Scheiben Brot mit Käse") — die KI schätzt die Kohlenhydrate
- **KE-Schätzung aus Foto**: 📷 Mahlzeit fotografieren, KI erkennt Lebensmittel, Portionen und berechnet KE
- **Modell**: OpenAI-kompatibles LLM mit Vision-Support (konfigurierbar über `BGMON_LLM_*`-Env-Vars)
- **Logbuch-Notiz bei ML-Training**: Nach jedem `flask predictor train` erscheint automatisch eine Notiz mit Modellversion, Sample-Anzahl und MAE-Werten

### BG-Prognose (ML)

Die BG-Prognose sagt den Blutzucker in 30, 60 und 120 Minuten voraus — basierend auf
den letzten Messwerten, Kohlenhydraten, Insulin, Basalrate und Tageszeit.

**Features (15 Eingabewerte pro Vorhersage):**

| Signal | Fenster |
|---|---|
| Aktueller BG, ∅ BG 30/60/120 min | 30 s–2 h |
| BG-Steigung (Trend) | 30 min, 60 min |
| Kohlenhydrate (KE) | 2 h, 4 h |
| Insulin (IE) | 2 h, 4 h |
| Basalrate, Wirkzeit, Korrekturfaktor | aus Settings |
| Tageszeit (sin/cos) | 24 h-Zyklus |

**Modell**: Pro Horizont eine separate `LinearRegression`, trainiert mit
Walk-Forward-Cross-Validation auf den historischen Daten.

**Aktivierung**: `BGMON_ML_ENABLED=true` in `.env`, dann einmalig `flask predictor train`
ausführen. Training und Evaluierung sind auch über Einstellungen → ML im Frontend
verfügbar (Admin-only, asynchron mit Status-Polling).

**Anzeige**: Im Dashboard erscheinen farbige Prognose-Linien im GlucoseGraph
(Blau = 30 min, Lila = 60 min, Orange = 120 min) mit Konfidenzbändern, sowie Prognose-Karten
in der StatsCard. Ein **Filter-Popup** (🔍) erlaubt das Ein-/Ausblenden historischer Prognose-Linien
zur Qualitätskontrolle („wie gut war die Vorhersage von vor 2 Stunden?").

> Die Prognose ist display-only — keine Alarmierung, keine Behandlungsempfehlung.

### PWA
- **Offline-fähig** via Service Worker
- **Installierbar** auf iOS, Android, Desktop

---

## Tech-Stack

| Komponente  | Technologie                              |
|-------------|------------------------------------------|
| Backend     | Python 3.14, Flask 3, SQLAlchemy 2       |
| Frontend    | Svelte 5, Vite 5, TypeScript             |
| Datenbank   | PostgreSQL 16                            |
| Time-Series | InfluxDB 2 (optional)                    |
| Telefonie   | Twilio Voice API                         |
| Push        | VAPID / Web-Push (`pywebpush`)           |
| Scheduler   | APScheduler mit Leader-Election          |
| WSGI        | Gunicorn (Produktion)                    |
| Container   | Docker, Docker Compose, Docker Swarm     |

---

## Installation

### Voraussetzungen
- Python ≥ 3.11 (3.14 empfohlen)
- Node.js ≥ 20
- PostgreSQL ≥ 14
- Optional: InfluxDB 2, Twilio-Account

---

### Variante A — Lokal (Entwicklung)

#### 1. Repository klonen
```bash
git clone https://github.com/mcfetz/bgmon.git
cd bgmon
```

#### 2. PostgreSQL & InfluxDB starten (am einfachsten via Docker)
```bash
docker compose up -d db influxdb
```

#### 3. Backend einrichten
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp ../.env.example ../.env
# .env bearbeiten — mindestens SECRET_KEY, DATABASE_URL, ggf. InfluxDB-Credentials

# Datenbank-Migrationen anwenden
flask --app bgmon_api.app db upgrade

# Dev-Server starten
flask --app bgmon_api.app run --debug --port 5000
```

#### 4. Frontend einrichten (zweites Terminal)
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Frontend: <http://localhost:5173>  
Backend:  <http://localhost:5000>

#### 5. Bootstrap-Admin

Beim ersten Start wird automatisch ein Admin-User angelegt, falls `BGMON_BOOTSTRAP_ADMIN_EMAIL` und `BGMON_BOOTSTRAP_ADMIN_PASSWORD` gesetzt sind.

---

### Variante B — Docker (Produktion)

#### 1. `.env` anlegen
```bash
cp .env.example .env
# Alle Platzhalter durch echte Werte ersetzen
```

#### 2. Container starten
```bash
docker compose up -d --build
```

Die App ist unter <http://localhost:5000> erreichbar.

> **Wichtig:** Der Scheduler läuft als **separater Prozess** (nicht in Gunicorn).
> Im Docker-Setup wird er automatisch via `docker compose` als zweiter Service
> gestartet. Bei manuellem Deployment:
> ```bash
> cd backend
> python3 run_scheduler.py
> ```

#### 3. ML-Modell trainieren (einmalig)
```bash
docker compose exec backend flask predictor train
```

#### 4. VAPID-Keys generieren (einmalig)
```bash
./scripts/generate-vapid-keys.sh
# Ausgabe in .env eintragen
```

#### 5. Docker Swarm (Hochverfügbarkeit)
```bash
make swarm-deploy
make swarm-ps
make swarm-logs
```

---

## Konfiguration

Alle Einstellungen werden über Umgebungsvariablen konfiguriert (siehe `.env.example`).

### Pflicht-Felder
| Variable                    | Beschreibung                                       |
|-----------------------------|----------------------------------------------------|
| `BGMON_SECRET_KEY`          | Flask-Session-Key. **In Produktion kryptisch generieren!** |
| `BGMON_DATABASE_URL`        | PostgreSQL-URL, z. B. `postgresql://user:pw@host/db` |
| `BGMON_PUBLIC_BASE_URL`     | Externe URL der App, z. B. `https://bgmon.example.com` |

### Optional — InfluxDB
| Variable                    | Beschreibung                                       |
|-----------------------------|----------------------------------------------------|
| `BGMON_INFLUXDB_URL`        | z. B. `https://influx.example.com`                 |
| `BGMON_INFLUXDB_TOKEN`      | API-Token mit Lese-Rechten auf den Bucket          |
| `BGMON_INFLUXDB_ORG`        | Organisation                                       |
| `BGMON_INFLUXDB_BUCKET`     | Bucket-Name (Standard: `gluroo`)                   |

### Optional — LibreLinkUp (CGM-Quelle)
| Variable                    | Beschreibung                                       |
|-----------------------------|----------------------------------------------------|
| `BGMON_LIBRE_EMAIL`         | LibreLinkUp-Login                                  |
| `BGMON_LIBRE_PASSWORD`      | LibreLinkUp-Passwort                               |
| `BGMON_LIBRE_REGION`        | `EU2`, `US`, `AU` etc.                             |

### Optional — Twilio (Anrufe)
| Variable                       | Beschreibung                                    |
|--------------------------------|-------------------------------------------------|
| `BGMON_TWILIO_ACCOUNT_SID`     | Twilio Account SID                              |
| `BGMON_TWILIO_AUTH_TOKEN`      | Twilio Auth Token                               |
| `BGMON_TWILIO_FROM_NUMBER`     | Absender-Nummer im E.164-Format                 |
| `BGMON_TWILIO_NUMBERS`         | Komma-getrennte Liste erlaubter Caller-IDs      |
| `BGMON_TWILIO_RETRY_COUNT`     | Wiederholungsversuche bei Fehler (Default: 3)   |
| `BGMON_TWILIO_RETRY_DELAY_S`   | Pause zwischen Versuchen in Sekunden (Default: 90) |

### Web-Push (VAPID)
| Variable            | Beschreibung                                          |
|---------------------|-------------------------------------------------------|
| `VAPID_PUBLIC_KEY`  | Wird im Frontend verwendet                            |
| `VAPID_PRIVATE_KEY` | Serverseitig zum Signieren                            |
| `VAPID_SUBJECT`     | `mailto:admin@example.com` oder `https://example.com` |

### ML-Prognose (optional)
| Variable                 | Beschreibung                                            |
|--------------------------|---------------------------------------------------------|
| `BGMON_ML_ENABLED`       | `true` aktiviert die BG-Prognose (Default: `false`)      |
| `BGMON_ML_MODEL_PATH`    | Pfad zu den trainierten Modell-Artifakten                |
| `BGMON_ML_HORIZONS`      | Komma-getrennte Vorhersage-Horizonte (Default: `30,60,120`) |

### KI-Integration (optional)
| Variable                 | Beschreibung                                            |
|--------------------------|---------------------------------------------------------|
| `BGMON_LLM_BASE_URL`     | OpenAI-kompatible API-URL (z. B. `https://api.openai.com/v1`) |
| `BGMON_LLM_MODEL`        | Modellname (z. B. `gpt-4o` für Text+Vision)              |
| `BGMON_LLM_API_KEY`      | API-Key für den LLM-Provider                              |

### Scheduler
| Variable                     | Beschreibung                                            |
|------------------------------|---------------------------------------------------------|
| `BGMON_DISABLE_SCHEDULER`    | `true` deaktiviert den Scheduler (Default: Scheduler aktiv) |

### Bootstrap (einmalig beim ersten Start)
| Variable                       | Beschreibung                                       |
|--------------------------------|----------------------------------------------------|
| `BGMON_BOOTSTRAP_ADMIN_EMAIL`  | Initiales Admin-Konto (nur beim ersten Start)      |
| `BGMON_BOOTSTRAP_ADMIN_PASSWORD` | Initiales Passwort                                |

### Leader-Election (Multi-Instance)
| Variable                       | Beschreibung                                       |
|--------------------------------|----------------------------------------------------|
| `BGMON_LEASE_TTL_S`            | Leader-Election TTL (Default: 30)                 |
| `BGMON_LEADER_RENEW_S`         | Leader-Renew-Intervall (Default: 10)               |

---

## API-Endpoints

Alle Endpoints sind unter `/api/*` gemountet. Session-Cookie erforderlich, außer bei `/auth/login` und `/health`.

### Auth
| Method | Endpoint              | Beschreibung                          |
|--------|-----------------------|---------------------------------------|
| POST   | `/api/auth/login`     | Login mit E-Mail + Passwort           |
| POST   | `/api/auth/logout`    | Session beenden                       |
| GET    | `/api/auth/me`        | Aktueller User                        |

### Dashboard
| Method | Endpoint                          | Beschreibung                                |
|--------|-----------------------------------|---------------------------------------------|
| GET    | `/api/dashboard/current`          | Aktueller Glukosewert + Trend               |
| GET    | `/api/dashboard/history?hours=24`  | Historische Werte                           |
| GET    | `/api/dashboard/stats`            | TIR / Statistik                             |
| GET    | `/api/dashboard/logs`             | Letzte Log-Einträge                         |
| GET    | `/api/dashboard/thresholds`       | Aktuelle Schwellwerte                       |

### Logbuch
| Method | Endpoint                | Beschreibung                          |
|--------|-------------------------|---------------------------------------|
| GET    | `/api/log/`             | Eigene Log-Einträge                   |
| POST   | `/api/log/`             | Neuen Eintrag erstellen               |
| PUT    | `/api/log/<id>`         | Eintrag bearbeiten                    |
| DELETE | `/api/log/<id>`         | Eintrag löschen                       |

### Nachtprofil & Schichten
| Method | Endpoint                  | Beschreibung                       |
|--------|---------------------------|------------------------------------|
| GET    | `/api/night/`             | Aktuelles Nachtprofil              |
| POST   | `/api/shifts/`            | Schicht starten                    |
| DELETE | `/api/shifts/<id>`        | Schicht beenden                    |

### Alarme & Push
| Method | Endpoint                          | Beschreibung                       |
|--------|-----------------------------------|------------------------------------|
| GET    | `/api/alarms/`                    | Alarm-Historie                     |
| POST   | `/api/alarms/push/subscribe`      | Push-Subscription speichern        |
| GET    | `/api/alarms/snooze`              | Aktueller Snooze                   |
| POST   | `/api/alarms/snooze`              | Snooze setzen                      |
| DELETE | `/api/alarms/snooze`              | Snooze aufheben                    |

### Familie-Dashboard
| Method | Endpoint                    | Beschreibung                          |
|--------|-----------------------------|---------------------------------------|
| GET    | `/api/family/<token>`       | Read-only-Snapshot (kein Login)       |

### Settings
| Method | Endpoint                          | Beschreibung                       |
|--------|-----------------------------------|------------------------------------|
| GET    | `/api/settings/global`            | Globale Einstellungen              |
| POST   | `/api/settings/thresholds`        | Schwellwerte aktualisieren         |
| POST   | `/api/settings/email`             | E-Mail ändern                      |
| POST   | `/api/settings/password`          | Passwort ändern                    |
| POST   | `/api/settings/twilio/test`       | Testanruf auslösen                 |

### Notifications (Profile)
| Method | Endpoint                            | Beschreibung                     |
|--------|-------------------------------------|----------------------------------|
| GET    | `/api/notifications/profiles`       | Alle Profile                     |
| POST   | `/api/notifications/profiles`       | Neues Profil                     |
| PUT    | `/api/notifications/profiles/<id>`  | Profil bearbeiten                |
| DELETE | `/api/notifications/profiles/<id>`  | Profil löschen                   |
| GET    | `/api/notifications/active`         | Aktives Profil                   |
| PUT    | `/api/notifications/active`         | Profil aktivieren                |

### User-Verwaltung (Admin)
| Method | Endpoint                | Beschreibung                          |
|--------|-------------------------|---------------------------------------|
| GET    | `/api/users/`           | Alle User                             |
| POST   | `/api/users/`           | User anlegen                          |
| PUT    | `/api/users/<id>`       | User bearbeiten                       |
| DELETE | `/api/users/<id>`       | User deaktivieren                     |

---

## Entwicklung

### Lint & Type-Check
```bash
make lint
# oder einzeln:
cd backend && ruff check . && ty check bgmon_api
cd frontend && npm run lint && npx tsc --noEmit
```

### Tests
```bash
make test
# CI nutzt PostgreSQL-Service-Container (siehe .github/workflows/ci.yml)
```

### VAPID-Keys generieren
```bash
./scripts/generate-vapid-keys.sh
```

### Code-Health-Check (eigener Wrapper)
```bash
./scripts/check.sh backend
./scripts/check.sh frontend
```

---

## Architektur-Highlights

- **Lazy Imports** in `models.py` und `auth_utils.py` vermeiden zirkuläre Imports zwischen Modellen und App-Factory
- **Leader-Election** via `scheduler_leader`-Tabelle — verhindert doppelte Alarm-Jobs in Multi-Instance-Setups
- **Per-User Schwellwerte** — Patient und Pflegende können unabhängige Alarmschwellen haben
- **Notification-Profile** entkoppeln *wer* alarmiert wird vom eigentlichen Schwellwert
- **Service Worker** im Frontend ermöglicht Offline-Nutzung und Background-Push

Siehe `AGENTS.md` für tieferes Architektur-Onboarding.

---

## Sicherheit

- **Passwörter**: bcrypt mit Default-Rounds
- **Sessions**: Flask sichere Cookies, `HttpOnly`, `SameSite=Lax`
- **CSRF**: Session-basierte Auth, SameSite-Cookies
- **Push**: VAPID-Signaturen, Subscription-IDs serverseitig gehasht
- **Secrets**: ausschließlich via `.env` (siehe `.env.example`)
- **DB-Migrations**: Alembic, idempotent

> **Wichtig**: `BGMON_SECRET_KEY` und alle Twilio-/InfluxDB-Credentials MÜSSEN in Produktion rotiert und über einen Secrets-Manager (z. B. Docker Swarm Secrets, HashiCorp Vault) bereitgestellt werden.

---

## Screenshots

| Dashboard | Alarm-Modal | Logbuch |
|---|---|---|
| ![](docs/screenshots/dashboard.png) | ![](docs/screenshots/alarm.png) | ![](docs/screenshots/log.png) |

*Platzhalter — Screenshots folgen*

---

## Lizenz

MIT — siehe [LICENSE](LICENSE).

---

## Mitwirkende

Entwickelt von [mcfetz](https://github.com/mcfetz) für den familiären Einsatz.

Pull Requests willkommen. Bitte zuerst `make lint && make test` ausführen.
