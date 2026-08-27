"""Notifications — Twilio (SMS + WhatsApp), avec fallback journal local.

Chaîne MVP : API → agent (alertes FR + fon) → notifications → mini-dashboard.

Sans credentials (démo/hackathon) : chaque notification est journalisée dans
artifacts/{city}/notifications.jsonl (le dashboard le montre en « local »).
Avec credentials, un vrai appel Twilio part :

  export TWILIO_ACCOUNT_SID=ACxxxx
  export TWILIO_AUTH_TOKEN=xxxx
  export TWILIO_TO=+2299XXXXXXXX      # destinataire (mobile Bénin)
  export TWILIO_FROM=+1XXXXXXXXXXXX   # numéro Twilio SMS
  export TWILIO_WHATSAPP_FROM=whatsapp:+14155238886   # (optionnel, WhatsApp)
"""

from __future__ import annotations

import json
import os

import httpx

from ..data.cities import DEFAULT_CITY

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TO = os.environ.get("TWILIO_TO", "")
FROM = os.environ.get("TWILIO_FROM", "")
WA_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "")


def _journal_path(city: str) -> str:
    p = os.path.join(BASE, "artifacts", city or DEFAULT_CITY, "notifications.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def build_message(alert: dict) -> str:
    """Message de notification : FR + fon + action principale."""
    lines = [f"{alert['message_fr']}"]
    if alert.get("message_fon"):
        lines.append(f"« {alert['message_fon']} »")
    if alert.get("actions_fr"):
        lines.append("Action: " + alert["actions_fr"][0])
    return "\n".join(lines)


def send_alert(alert: dict) -> dict:
    """Envoie l'alerte par Twilio si configuré, sinon la journalise (mode local).

    Retourne {"channel": "whatsapp"|"sms"|"local", "ok": bool, "to": str}.
    """
    msg = build_message(alert)
    rec = {"ts": alert["ts"], "node": alert["node"], "level": alert["level"],
           "channel": "local", "ok": False, "to": "journal local",
           "message": msg[:300]}

    if SID and TOKEN and TO:
        use_wa = bool(WA_FROM)
        payload = {
            "From": WA_FROM if use_wa else FROM,
            "To": f"whatsapp:{TO}" if use_wa else f"smpp:{TO}",
            "Body": msg,
        }
        try:
            r = httpx.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json",
                auth=(SID, TOKEN), data=payload, timeout=10,
            )
            rec["channel"] = "whatsapp" if use_wa else "sms"
            rec["to"] = TO
            rec["ok"] = r.status_code in (200, 201)
            if not rec["ok"]:
                rec["error"] = f"HTTP {r.status_code}: {r.text[:120]}"
        except httpx.HTTPError as e:
            rec["error"] = str(e)[:120]
    else:
        # mode démo : journal local (visible dans le dashboard + lisible par l'équipe)
        try:
            with open(_journal_path(alert.get("city", DEFAULT_CITY)), "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass

    return rec
