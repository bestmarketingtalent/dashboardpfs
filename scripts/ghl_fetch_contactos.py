#!/usr/bin/env python3
"""Descarga READ-ONLY de la tabla completa de contactos de GHL (PFS Realty) con sus
campos personalizados (Lead Status, En curso por, Realtor, interacción, etc.).
Usa POST /contacts/search, que es un endpoint de CONSULTA paginada: no escribe,
no modifica ni borra nada en el CRM. Escribe scripts/data/contacts.json."""
import json, time, urllib.request, sys
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
       "User-Agent": "curl/8.4.0", "Content-Type": "application/json"}

# Campos personalizados de contacto que usa el reporte (ids fijos de la subcuenta PFS)
CF = {
    'jgBUd3g0oNAE46OyrqT4': 'leadStatus',      # Lead Status
    'FhyfsuBrhDu2i30jFtkE': 'enCursoPor',      # En curso por
    'PAZfvdHwy8xNDg2Q85C4': 'realtor',         # Realtor (multi)
    'iaAS762HfiWyLlzGd7Q3': 'nivelInteres',    # Nivel de Interés
    'p9hh01Q901hm3vb0Brog': 'vecesContactado', # Number of times contacted
    '2F2FJMO8SWeGWsTB0OhH': 'salesActivities', # Number of sales activities
    'K9MAaG6HGiFdYC4U8FP8': 'lastActivity',    # Last activity date
    'K5MGeEwjcQ4yPLf41KrP': 'lastEngagement',  # Last Engagement Date
    'Ze9PczkkwtkPQFnREB7m': 'riesgoPerdida',   # Riesgo de Pérdida del Lead
    'jmw3tBCaAOh4zv9U4QIM': 'visaVigente',    # Tienes Visa Vigente
    'VRgySOgMR8Gc6uODKI6P': 'interesCredito', # Interesado en crédito hipotecario
    'SwwhljT2SwbvS5vMhydr': 'tipoPropiedad',  # Tipo de Propiedad de Interés
    'q4YlHWDc1ZViOaGgDPON': 'intencionInv',   # Intencion de Inversion
    'vJbtvCzJQYmpvnkoovIY': 'tipoInversion',  # Tipo de Inversión
    'gRdayE27ahUMkLQc14CP': 'presupuesto',    # Presupuesto de compra
    'AKmGcU9YQOS30Oq91VZX': 'tiempoInv',      # Tiempo estimado de inversión
    'lpvyGJ1ZhyJsNx4yynaL': 'ciudadRes',      # Ciudad de Residencia
    'jnBoWYoG9ntIySIAI7wJ': 'actividadEco',   # Actividad economica
    '0lbAhx4sZbSdO5ZfdAnp': 'hobbies',        # Hobbies
    'FrbupGpEGH061BlyF90G': 'zonaInteres',    # Zona de interés
    '59pSOsLKDt5du1SAXNrU': 'anoCompra',      # Posible Año de Compra
    '5ZeTQM8FkWc6kok2sQaX': 'motivoDescarte', # Motivo de descarte
}

def search(body):
    req = urllib.request.Request(f"{BASE}/contacts/search",
                                 data=json.dumps(body).encode(), headers=HDR)  # búsqueda: solo consulta
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            print(f"  retry {i+1}: {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    raise SystemExit("fallo definitivo en /contacts/search")

contacts, page, search_after = [], 1, None
while True:
    body = {"locationId": L, "pageLimit": 500}
    if search_after: body["searchAfter"] = search_after
    d = search(body)
    batch = d.get("contacts", [])
    if not batch: break
    for c in batch:
        name = (c.get("contactName") or f"{c.get('firstName') or ''} {c.get('lastName') or ''}").strip()
        rec = {
            "id": c["id"], "name": name,
            "email": c.get("email") or "", "phone": c.get("phone") or "",
            "tags": c.get("tags") or [],
            "source": (c.get("source") or "").strip(),
            "assigned": c.get("assignedTo") or "",
            "created": c.get("dateAdded"),
            "country": c.get("country") or "",
        }
        for f in (c.get("customFields") or []):
            k = CF.get(f.get("id"))
            if k: rec[k] = f.get("value")
        # atribución de la sesión de origen (se llena cuando el lead entra por
        # formulario/landing con UTMs o gclid; si entra por WhatsApp queda solo el medio)
        attr = c.get("attributionSource") or {}
        attr_min = {k: attr[k] for k in ("sessionSource", "medium", "utmSource", "utmMedium",
                                          "utmCampaign", "campaign", "gclid", "fbclid",
                                          "adName", "campaignId") if attr.get(k)}
        if attr_min: rec["attr"] = attr_min
        contacts.append(rec)
    search_after = batch[-1].get("searchAfter")
    total = d.get("total")
    if page % 10 == 0 or len(contacts) >= (total or 0) or not search_after:
        print(f"pagina {page}: acumulado {len(contacts)} / {total}")
    if len(contacts) >= (total or 0) or not search_after: break
    page += 1
    time.sleep(0.15)

json.dump(contacts, open(DATA / "contacts.json", "w"), ensure_ascii=False)
print(f"LISTO: {len(contacts)} contactos -> {DATA / 'contacts.json'}")
