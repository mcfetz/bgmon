# BG-Prognose v1

Patientenspezifische 60-/120-Minuten-Vorhersage aus historischen Glukosewerten, Kohlenhydraten, Insulin, Basalrate und Tageszeit. Display-only — keine Alarmierung, keine Behandlungsempfehlung.

## Technik

- **Modelle**: `scikit-learn` `LinearRegression`, je ein Modell pro Horizont (60 min, 120 min)
- **Features**: BG-Verlauf (letzte 30/60/90/120 min), KE/Insulin/ Basal im Fenster, Tageszeit (sin/cos), patientenspezifische Settings
- **Training**: Walk-Forward-Cross-Validation mit horizon-aware Split — passiert komplett offline, nie im Request-Pfad
- **Persistenz**: `PredictionRun` / `PredictionPoint` in PostgreSQL, `joblib`-Artifacts auf Disk
- **Runtime**: Lazy-Load pro Prozess, Same-Context-Erkennung (kein Doppel-Predict bei Dashboard-Refresh)

## Konfiguration

In `.env`:

```bash
# Aktivieren (default: false)
BGMON_ML_ENABLED=true

# Modell-Verzeichnis (default: backend/ml_models/bg_prediction_v1/)
# BGMON_ML_MODEL_PATH=

# Vorhersage-Horizonte in Minuten (default: 60,120)
# BGMON_ML_HORIZONS=60,120
```

## Modell trainieren

```bash
cd backend
source .venv/bin/activate
export FLASK_APP=bgmon_api.app:create_app

# Training ausführen
flask predictor train
```

Ausgabe:

```
✓ Published models to backend/ml_models/bg_prediction_v1
  manifest: …/manifest.json
  samples:  1234
  60m:  baseline_mae=25.3  model_mae=12.1  (n_splits=5)
  120m: baseline_mae=28.7  model_mae=16.4  (n_splits=5)
```

**Wann neu trainieren?** Nach 1–2 Wochen neuen Daten, nach Settings-Änderungen (KE-Faktor, Korrekturfaktor), oder einfach regelmäßig per Cron.

## Modell evaluieren

```bash
flask predictor evaluate

# Maschinenlesbar:
flask predictor evaluate --json-output
```

Vergleicht alle gespeicherten Vorhersagen mit später eingetroffenen echten Messwerten und zeigt MAE (Mean Absolute Error) pro Horizont und Modellversion.

## Im Dashboard

Wenn ML aktiviert und Modell trainiert ist:

| Komponente | Was erscheint |
|---|---|
| **GlucoseGraph** | Gestrichelte hellblaue Linie ab letztem Messwert in die Zukunft, dahinter transluzentes Konfidenzband |
| **StatsCard** | Neue Karte „Prognose +60min“ mit vorhergesagtem Wert und Konfidenzintervall (z.B. „142  (128–156) mg/dL") |

Nichts erscheint, keine Fehler — Prognose degradiert lautlos wenn deaktiviert oder kein Modell vorhanden.

## Docker-Deployment

```bash
# 1. Image bauen (CI macht das automatisch bei Push)
docker compose build backend

# 2. Container starten
docker compose up -d

# 3. Einmalig trainieren
docker compose exec backend flask predictor train

# 4. Optional: Cron-Job für regelmäßiges Retraining
# 0 3 * * 1 cd /pfad/zu/bgmon && docker compose exec -T backend flask predictor train
```

## Troubleshooting

| Symptom | Ursache | Lösung |
|---|---|---|
| Dashboard zeigt keine Prognose | `BGMON_ML_ENABLED` nicht gesetzt | `.env` prüfen, Container neu starten |
| API gibt 503 `"unavailable"` | Kein `manifest.json` oder Modelle fehlen | `flask predictor train` ausführen |
| API gibt 422 `"insufficient_context"` | Weniger als 30 min BG-Daten | Normal bei frischem Start, löst sich von selbst |
| Training schlägt fehl | Zu wenig Daten (< 3 Samples mit beiden Horizonten) | Mehr Daten sammeln (mindestens ein paar Tage) |
| `flask` findet `predictor`-Befehl nicht | CLI nicht registriert | `export FLASK_APP=bgmon_api.app:create_app` |