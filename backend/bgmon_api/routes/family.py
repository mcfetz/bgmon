# ruff: noqa: E501
"""Family dashboard — read-only access via secret token URL.

Primary storage: PostgreSQL (GlucoseReading model).
"""

from http import HTTPStatus

from flask import Blueprint, jsonify
from flask import Response as FlaskResponse

from bgmon_api.models import FamilyDashboardToken, GlucoseReading
from bgmon_api.utils import compute_glucose_stats

family_bp = Blueprint("family", __name__)


def _verify_token(token: str) -> FamilyDashboardToken | None:
    return FamilyDashboardToken.query.filter_by(token=token).first()


@family_bp.route("/<token>", methods=["GET"])
def dashboard(token: str) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    entry = _verify_token(token)
    if not entry:
        return jsonify({"error": "invalid token"}), HTTPStatus.NOT_FOUND

    current = (
        GlucoseReading.query
        .order_by(GlucoseReading.timestamp.desc())
        .first()
    )
    current_data = {
        "sgv": current.sgv if current else None,
        "trend": current.trend if current else None,
        "direction": current.direction if current else None,
        "timestamp": current.timestamp.isoformat() if current and current.timestamp else None,
    }

    from datetime import UTC, datetime, timedelta
    since = datetime.now(UTC) - timedelta(hours=24)
    readings = (
        GlucoseReading.query
        .filter(GlucoseReading.timestamp >= since)
        .order_by(GlucoseReading.timestamp.asc())
        .all()
    )
    values = [r.sgv for r in readings if r.sgv is not None]
    stats = compute_glucose_stats(values)

    return jsonify({
        "current": current_data,
        "stats": stats,
        "token_valid": True,
    })


@family_bp.route("/<token>/current", methods=["GET"])
def current_glucose(token: str) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    entry = _verify_token(token)
    if not entry:
        return jsonify({"error": "invalid token"}), HTTPStatus.NOT_FOUND

    current = (
        GlucoseReading.query
        .order_by(GlucoseReading.timestamp.desc())
        .first()
    )
    return jsonify({
        "sgv": current.sgv if current else None,
        "trend": current.trend if current else None,
        "direction": current.direction if current else None,
        "timestamp": current.timestamp.isoformat() if current and current.timestamp else None,
    })


@family_bp.route("/view/<token>", methods=["GET"])
def viewer(token: str) -> FlaskResponse | tuple[FlaskResponse, HTTPStatus]:
    entry = _verify_token(token)
    if not entry:
        return FlaskResponse("<h1>Ungultiger Token</h1>", status=404)

    return FlaskResponse(_FAMILY_HTML.replace("{TOKEN}", token), mimetype="text/html")


_FAMILY_HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>bgmon &mdash; Familien-Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
background:#0f172a;color:#f8fafc;min-height:100vh;
display:flex;flex-direction:column;align-items:center;
justify-content:center;padding:1rem}
.loader{font-size:1.2rem;color:#94a3b8}
.loading{text-align:center}
.error{color:#f87171;text-align:center;font-size:1.1rem}
.value{font-size:min(20vw,20vh,180px);font-weight:800;line-height:1;
font-variant-numeric:tabular-nums}
.unit{font-size:clamp(1rem,3vw,1.5rem);color:#94a3b8}
.trend{font-size:min(15vw,15vh,120px);line-height:1}
.time{font-size:.9rem;color:#64748b;margin-top:.5rem}
.in-range{color:#22c55e}
.borderline{color:#eab308}
.critical{color:#ef4444}
@media(prefers-color-scheme:light){
body{background:#f8fafc;color:#0f172a}
.unit{color:#64748b}
.time{color:#94a3b8}
}
</style>
</head>
<body>
<div id="app" class="loading"><span class="loader">Lade...</span></div>
<script>
var T="{TOKEN}";
var A="/api/family/"+T+"/current";
function t(d){return{DoubleUp:"\u21c8",SingleUp:"\u2191",FortyFiveUp:"\u2197",Flat:"\u2192",FortyFiveDown:"\u2198",SingleDown:"\u2193",DoubleDown:"\u21ca"}[d]||"\u2192"}
function c(v){if(v==null)return"";if(v<54||v>250)return"critical";if(v<70||v>180)return"borderline";return"in-range"}
function g(ts){if(!ts)return"\u2014";var d=Date.now()-new Date(ts).getTime();var s=Math.floor(d/1000);if(s<60)return"vor "+s+" Sek.";var m=Math.floor(s/60);if(m<60)return"vor "+m+" Min.";return"vor "+Math.floor(m/60)+" Std."}
async function r(){try{var x=await fetch(A);if(!x.ok){E("Keine Daten");return}var j=await x.json();var v=j.sgv;if(v==null){E("Keine Daten");return}var h=document.getElementById("app");h.innerHTML='<div class="value '+c(v)+'">'+v+'</div><div class="unit">mg/dL</div><div class="trend '+c(v)+'">'+t(j.direction)+'</div><div class="time">'+g(j.timestamp)+'</div>'}catch(e){E("Verbindungsfehler")}}
function E(m){document.getElementById("app").innerHTML='<span class="error">'+m+'</span>'}
r();setInterval(r,60000);
</script>
</body>
</html>
"""
