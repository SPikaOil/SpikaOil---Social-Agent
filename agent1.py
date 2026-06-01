"""
Agent 1 — Soul ID Creator
Maakt een consistente AI persona aan via Higgsfield Soul.
Eenmalig per product uitvoeren — NA Agent 0, VOOR Agent 2.

Gebruik:
  python agent1.py --product-id 14
  python agent1.py --product-naam "SPika Oil"
"""

import urllib.request
import urllib.error
import json
import time
import os
import argparse
import urllib.parse
import base64
import sys
from config import (
    SUPABASE_URL, SUPABASE_KEY,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    HIGGSFIELD_KEY, HIGGSFIELD_API_ID
)

HIGGSFIELD_AUTH = f"Basic {base64.b64encode(f'{HIGGSFIELD_API_ID}:{HIGGSFIELD_KEY}'.encode()).decode()}"

# 20 hoeken voor Soul ID training
SOUL_HOEKEN = [
    ("frontaal neutraal",        "looking directly at camera, neutral expression"),
    ("frontaal lichte glimlach", "looking directly at camera, slight warm smile"),
    ("frontaal serieus",         "looking directly at camera, serious confident expression"),
    ("frontaal meditief",        "looking directly at camera, calm meditative expression"),
    ("3/4 links",                "three quarter view left, looking slightly left, calm"),
    ("3/4 rechts",               "three quarter view right, looking slightly right, slight smile"),
    ("profiel links",            "side profile left, elegant posture"),
    ("profiel rechts",           "side profile right, calm expression"),
    ("hoek omhoog",              "slightly high angle, looking up at camera, open expression"),
    ("hoek omlaag",              "slightly low angle, looking slightly down, confident"),
    ("close-up ogen",            "extreme close-up face, eyes looking at camera, calm"),
    ("close-up glimlach",        "close-up face, warm genuine smile"),
    ("hoofd schuin rechts",      "head tilted slightly right, warm natural expression"),
    ("hoofd schuin links",       "head tilted slightly left, thoughtful expression"),
    ("ogen gesloten",            "eyes gently closed, peaceful meditative expression"),
    ("omhoog kijkend",           "looking slightly up and to the right, contemplative"),
    ("neer kijkend",             "looking gently downward, serene expression"),
    ("over schouder links",      "over shoulder left, looking back at camera, subtle smile"),
    ("over schouder rechts",     "over shoulder right, looking back at camera, confident"),
    ("3/4 glimlach",             "three quarter view, warm confident smile, direct energy"),
]

# ============================================================
# HELPERS
# ============================================================

def supabase_get(tabel, filter=""):
    url = f"{SUPABASE_URL}/rest/v1/{tabel}"
    if filter:
        url += f"?{filter}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("apikey",        SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"[Supabase] Fout: {e.code}")
        return []


def supabase_patch(tabel, filter, data):
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{tabel}?{filter}",
        data=payload, method="PATCH"
    )
    req.add_header("apikey",        SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Content-Type",  "application/json")
    try:
        with urllib.request.urlopen(req):
            return True
    except urllib.error.HTTPError as e:
        print(f"[Supabase] Patch fout: {e.code} - {e.read().decode()[:200]}")
        return False


def higgsfield_beschikbaar():
    """Checkt of Higgsfield beschikbaar is."""
    if not HIGGSFIELD_KEY or not HIGGSFIELD_API_ID:
        return False
    try:
        import higgsfield_client
        os.environ["HF_API_KEY"]    = HIGGSFIELD_API_ID
        os.environ["HF_API_SECRET"] = HIGGSFIELD_KEY
        return True
    except ImportError:
        print("[Agent 1] higgsfield-client niet geïnstalleerd")
        print("Voer uit: pip install higgsfield-client")
        return False


# ============================================================
# SOUL ID GENERATIE
# ============================================================

def genereer_portret(basis_prompt, hoek_beschrijving, hoek_prompt):
    """Genereert één portretfoto via Higgsfield Soul 2.0."""
    import higgsfield_client

    volledige_prompt = (
        f"{basis_prompt}, {hoek_prompt}, "
        "soft natural window light from the left, "
        "clean white background, shallow depth of field, "
        "premium lifestyle aesthetic, no text, no watermark"
    )

    try:
        result = higgsfield_client.subscribe(
            "higgsfield-ai/soul/standard",
            arguments={
                "prompt":       volledige_prompt,
                "resolution":   "720p",
                "aspect_ratio": "2:3"
            }
        )

        # Haal URL op
        jobs = result.get("jobs", [])
        if jobs:
            url = (jobs[0].get("results", {}).get("raw", {}).get("url") or
                   jobs[0].get("results", {}).get("min", {}).get("url"))
            if url:
                return url

        images = result.get("images", [])
        if images:
            return images[0].get("url", "")

        return None

    except Exception as e:
        print(f"  [Soul] Fout bij {hoek_beschrijving}: {str(e)[:100]}")
        return None


def genereer_20_portetten(soul_persona):
    """Genereert 20 portretfoto's van dezelfde persona."""
    naam     = soul_persona.get("naam", "Persona")
    leeftijd = soul_persona.get("leeftijd", "30 jaar")
    uiterlijk = soul_persona.get("uiterlijk", "natural makeup, dark hair")
    stijl    = soul_persona.get("stijl", "minimal jewelry, wellness lifestyle")

    basis_prompt = (
        f"Portrait photo of a {leeftijd} woman named {naam}, "
        f"{uiterlijk}, {stijl}, same person in every photo"
    )

    print(f"[Agent 1] 20 portetten genereren voor {naam}...")
    print(f"[Agent 1] Basis: {basis_prompt[:80]}...")

    urls = []
    for i, (beschrijving, hoek_prompt) in enumerate(SOUL_HOEKEN, 1):
        print(f"  [{i}/20] {beschrijving}...")
        url = genereer_portret(basis_prompt, beschrijving, hoek_prompt)

        if url:
            urls.append({
                "nummer": i,
                "hoek":   beschrijving,
                "url":    url
            })
            print(f"  ✓ {url[:60]}...")
        else:
            print(f"  ✗ Mislukt — overgeslagen")

        # Rate limit
        if i < len(SOUL_HOEKEN):
            time.sleep(2)

    print(f"\n[Agent 1] {len(urls)}/20 portetten gegenereerd")
    return urls


def registreer_soul_id(naam, portret_urls):
    """Registreert de portetten als Soul ID via Higgsfield API."""
    if not portret_urls:
        print("[Agent 1] Geen portetten — Soul ID niet aangemaakt")
        return None

    print(f"[Agent 1] Soul ID registreren met {len(portret_urls)} portetten...")

    input_images = [
        {"type": "IMAGE_URL", "image_url": p["url"]}
        for p in portret_urls
    ]

    payload = json.dumps({
        "name":         naam.replace(" ", "_"),
        "input_images": input_images
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://cloud.higgsfield.ai/api/v1/soul-ids",
        data=payload, method="POST"
    )
    req.add_header("Authorization", HIGGSFIELD_AUTH)
    req.add_header("Content-Type",  "application/json")

    try:
        with urllib.request.urlopen(req) as r:
            result  = json.loads(r.read().decode())
            soul_id = result.get("id") or result.get("soul_id")
            if soul_id:
                print(f"[Agent 1] ✓ Soul ID aangemaakt: {soul_id}")
                return soul_id
    except urllib.error.HTTPError as e:
        print(f"[Agent 1] Soul ID registratie fout: {e.code} - {e.read().decode()[:200]}")

    # Fallback — sla eerste portret URL op
    eerste_url = portret_urls[0]["url"] if portret_urls else ""
    print(f"[Agent 1] Registratie mislukt — portret URL opgeslagen voor handmatige upload")
    print(f"[Agent 1] Upload handmatig op: higgsfield.ai/soul")
    print(f"[Agent 1] Portret URL: {eerste_url}")
    return None


# ============================================================
# BRAND LOCK TEMPLATE GENEREREN
# ============================================================

def genereer_brand_lock_template(product):
    """
    Genereert de vaste brand lock prompt template voor dit product.
    Wordt opgeslagen in Supabase en gebruikt door Agent 4 bij elke video.
    """
    print("[Agent 1] Brand lock template genereren...")

    pk       = product.get("primaire_kleur", "")
    sk       = product.get("secondaire_kleur", "")
    soul_hex = product.get("soul_hex_kleuren", "")
    vibe     = product.get("vibe_beschrijving", "")
    tempo    = product.get("editing_tempo", "slow cinematic")
    grading  = product.get("editing_kleurgrading", "warm, soft, premium")
    prod_ref = product.get("product_reference_prompt", "")

    brand_lock = {
        "brand_open": (
            f"Cinematic {tempo} shot. "
            f"Color palette: {pk}, {sk}. "
            f"{grading} color grading. "
            f"{vibe} "
        ),
        "brand_close": (
            f"Product visible: {prod_ref[:100] if prod_ref else 'product in frame'}. "
            f"Premium brand aesthetic. 9:16 vertical. No text, no logo."
        ),
        "soul_hex":    soul_hex,
        "instructie":  "Gebruik brand_open aan het begin en brand_close aan het einde van elke Higgsfield prompt."
    }

    print("[Agent 1] ✓ Brand lock template gegenereerd")
    return brand_lock


# ============================================================
# HOOFDFUNCTIES
# ============================================================

def haal_product_op(product_id=None, product_naam=None):
    """Haalt product op uit Supabase."""
    if product_id:
        data = supabase_get("producten", f"select=*&id=eq.{product_id}")
    elif product_naam:
        naam_encoded = urllib.parse.quote(product_naam)
        data = supabase_get("producten", f"select=*&product_naam=eq.{naam_encoded}")
    else:
        data = supabase_get("producten", "select=*&status=eq.Actief&order=id.desc&limit=1")

    if not data:
        print("[Agent 1] Geen product gevonden")
        return None

    product = data[0]
    print(f"[Agent 1] Product geladen: {product.get('product_naam')} (ID: {product.get('id')})")
    return product


def run(product_id=None, product_naam=None):
    """Voert Agent 1 uit — Soul ID aanmaken."""
    print("\n" + "=" * 60)
    print("  AGENT 1 — SOUL ID CREATOR")
    print("  Eenmalig per product uitvoeren")
    print("=" * 60)

    # Haal product op
    product = haal_product_op(product_id, product_naam)
    if not product:
        return {"success": False, "bericht": "Product niet gevonden"}

    pid  = product.get("id")
    naam = product.get("product_naam", "")

    # Check of Soul ID al bestaat
    if product.get("soul_id"):
        print(f"[Agent 1] Soul ID al aangemaakt: {product.get('soul_id')} — overslaan")
        return {"success": True, "bericht": "Soul ID al beschikbaar", "soul_id": product.get("soul_id")}

    # Check of soul_id_persona beschikbaar is
    soul_persona = product.get("soul_id_persona", {}) or {}
    if isinstance(soul_persona, str):
        try:
            soul_persona = json.loads(soul_persona)
        except:
            soul_persona = {}

    if not soul_persona:
        print("[Agent 1] Geen soul_id_persona gevonden — eerst Agent 0 uitvoeren")
        return {"success": False, "bericht": "soul_id_persona ontbreekt — voer Agent 0 eerst uit"}

    print(f"\n[Agent 1] Persona: {soul_persona.get('naam', 'Onbekend')}")
    print(f"[Agent 1] Uiterlijk: {soul_persona.get('uiterlijk', '')[:60]}")

    # Genereer brand lock template (altijd — ongeacht Higgsfield beschikbaarheid)
    brand_lock = genereer_brand_lock_template(product)
    supabase_patch("producten", f"id=eq.{pid}", {"brand_lock_template": brand_lock})

    # Check Higgsfield beschikbaarheid
    if not higgsfield_beschikbaar():
        print("[Agent 1] Higgsfield niet beschikbaar — brand lock template opgeslagen")
        print("[Agent 1] Voeg Higgsfield API key toe aan config.py voor Soul ID generatie")
        return {
            "success":    True,
            "bericht":    "Brand lock template opgeslagen — Higgsfield nodig voor Soul ID",
            "brand_lock": brand_lock
        }

    # Genereer 20 portetten
    portret_urls = genereer_20_portetten(soul_persona)

    # Registreer als Soul ID
    soul_id = registreer_soul_id(f"{naam}_Soul", portret_urls)

    # Sla op in Supabase
    update_data = {
        "soul_id":             soul_id or "",
        "soul_id_portret_url": portret_urls[0]["url"] if portret_urls else "",
        "brand_lock_template": brand_lock
    }
    supabase_patch("producten", f"id=eq.{pid}", update_data)

    print("\n" + "=" * 60)
    print("  AGENT 1 KLAAR")
    print(f"  Product: {naam}")
    print(f"  Soul ID: {soul_id or 'Portret opgeslagen — handmatig registreren op higgsfield.ai/soul'}")
    print(f"  Portetten: {len(portret_urls)}/20 gegenereerd")
    print("  Brand lock template opgeslagen in Supabase")
    print("  Volgende stap: python agent2.py")
    print("=" * 60)

    return {
        "success":      True,
        "product_id":   pid,
        "soul_id":      soul_id,
        "portret_urls": portret_urls,
        "brand_lock":   brand_lock,
        "bericht":      f"Soul ID aangemaakt voor {naam}"
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 1 — Soul ID Creator")
    parser.add_argument("--product-id",   type=int, help="Supabase product ID")
    parser.add_argument("--product-naam", type=str, help="Product naam")
    args = parser.parse_args()

    resultaat = run(
        product_id=args.product_id,
        product_naam=args.product_naam
    )

    print(f"\nResultaat: {json.dumps({k: v for k, v in resultaat.items() if k not in ['portret_urls', 'brand_lock']}, indent=2, ensure_ascii=False)}")
