#!/usr/bin/env python3
"""Descarga READ-ONLY (solo GET) de oportunidades, usuarios y pipelines de GHL (PFS Realty).
Credenciales desde el .env del proyecto. Escribe JSONs en scripts/data/."""
import json, time, urllib.request, urllib.parse, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / 'data'
DATA.mkdir(exist_ok=True)
ENV = {}
for line in (ROOT / '.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1); ENV[k] = v
T = ENV['GHL_PIT']
L = ENV['GHL_LOCATION_ID']
BASE = "https://services.leadconnectorhq.com"
HDR = {"Authorization": f"Bearer {T}", "Version": "2021-07-28", "Accept": "application/json",
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

# Pipelines
pipes = get(f"{BASE}/opportunities/pipelines?locationId={L}")
json.dump(pipes, open(DATA / "pipelines.json", "w"), ensure_ascii=False)
print(f"pipelines: {len(pipes.get('pipelines', []))}")

# Usuarios
users = get(f"{BASE}/users/?locationId={L}").get("users", [])
json.dump(users, open(DATA / "users.json", "w"), ensure_ascii=False)
print(f"usuarios: {len(users)}")

# Oportunidades paginadas
opps, page = [], 1
url = f"{BASE}/opportunities/search?location_id={L}&limit=100"
while url:
    d = get(url)
    batch = d.get("opportunities", [])
    for o in batch:
        c = o.get("contact") or {}
        rel = (o.get("relations") or [{}])[0]
        opps.append({
            "id": o["id"], "stage": o.get("pipelineStageId"),
            "pipeline": o.get("pipelineId"), "status": o.get("status"),
            "source": (o.get("source") or "").strip(),
            "assigned": o.get("assignedTo") or "",
            "created": o.get("createdAt"), "stageChange": o.get("lastStageChangeAt"),
            "value": o.get("monetaryValue") or 0,
            "lostReason": o.get("lostReasonId"),
            "name": c.get("name") or rel.get("fullName") or "",
            "email": c.get("email") or "", "phone": c.get("phone") or "",
            "tags": c.get("tags") or [],
        })
    meta = d.get("meta", {})
    url = meta.get("nextPageUrl")
    if page % 20 == 0 or not url:
        print(f"pagina {page}: acumulado {len(opps)} / {meta.get('total')}")
    page += 1
    time.sleep(0.12)

json.dump(opps, open(DATA / "opps.json", "w"), ensure_ascii=False)
print(f"LISTO: {len(opps)} oportunidades -> {DATA / 'opps.json'}")
