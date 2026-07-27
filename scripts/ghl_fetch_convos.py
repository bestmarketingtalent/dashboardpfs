#!/usr/bin/env python3
"""Descarga READ-ONLY (solo GET) de la metadata de TODAS las conversaciones de GHL
(PFS Realty): id, contacto, asesor, canal, último mensaje (dirección, fecha, texto).
Escribe scripts/data/convos.json. No modifica nada en el CRM."""
import json, time, urllib.request, urllib.parse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'
ENV = {}
for line in (ROOT / '.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1); ENV[k] = v
T, L = ENV['GHL_PIT'], ENV['GHL_LOCATION_ID']
BASE = "https://services.leadconnectorhq.com"
HDR = {"Authorization": f"Bearer {T}", "Version": "2021-04-15", "Accept": "application/json",
       "User-Agent": "curl/8.4.0"}

def get(url):
    req = urllib.request.Request(url, headers=HDR)  # GET only
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            print(f"  retry {i+1}: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise SystemExit("fallo definitivo: " + url)

convos, page, start_after = [], 1, None
while True:
    q = {"locationId": L, "limit": 100, "sort": "desc", "sortBy": "last_message_date"}
    if start_after: q["startAfterDate"] = start_after
    d = get(f"{BASE}/conversations/search?{urllib.parse.urlencode(q)}")
    batch = d.get("conversations", [])
    if not batch: break
    for c in batch:
        convos.append({
            "id": c["id"], "contactId": c.get("contactId"),
            "assigned": c.get("assignedTo") or "",
            "lastType": c.get("lastMessageType") or "",
            "lastDir": c.get("lastMessageDirection") or "",
            "lastDate": c.get("lastMessageDate"),
            "lastBody": (c.get("lastMessageBody") or "")[:200],
            "unread": c.get("unreadCount") or 0,
        })
    start_after = batch[-1].get("sort", [None])[-1]
    total = d.get("total")
    if page % 20 == 0 or not start_after:
        print(f"pagina {page}: acumulado {len(convos)} / {total}")
    if not start_after or (total and len(convos) >= total): break
    page += 1
    time.sleep(0.12)

json.dump(convos, open(DATA / "convos.json", "w"), ensure_ascii=False)
print(f"LISTO: {len(convos)} conversaciones -> {DATA / 'convos.json'}")
