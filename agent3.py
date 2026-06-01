"""
Agent 3 — Script Maker
Schrijft 2x 8-seconden video scripts op basis van brand manual + Agent 2 research.

Gebruik:
  python agent3.py --product-id 14
  python agent3.py --product-naam "SPika Oil"
"""

import urllib.request
import urllib.error
import json
import time
import os
import argparse
import urllib.parse
from config import (
    SUPABASE_URL, SUPABASE_KEY,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL
)

# ============================================================
# SYSTEM PROMPT
# ============================================================

AGENT_3_PROMPT = """
Je bent een expert video script schrijver voor 8-seconden Instagram Reels en TikTok videos.

KRITIEKE REGELS:
- Elke video is EXACT 8 seconden
- Maximaal 3 shots per video
- On-screen tekst: maximaal 5 woorden per shot
- Gebruik ALTIJD hooks uit de hook_bibliotheek
- Gebruik ALTIJD CTAs uit de cta_bibliotheek
- Volg de merkarchitectuur — wat altijd/nooit in beeld
- Schrijf video prompts in het Engels voor Higgsfield AI
- Return ALLEEN pure JSON — geen markdown, geen backticks

OUTPUT FORMAT:
{
  "product_naam": "",
  "script_1": {
    "format": "UGC/productshot/testimonial/how-to",
    "hook": "",
    "shots": [
      {
        "tijdstip": "0:00-0:03",
        "beeld": "",
        "camerahoek": "",
        "beweging": "",
        "onscreen_tekst": ""
      }
    ],
    "cta": "",
    "caption_instagram": "",
    "caption_tiktok": "",
    "muziek": "",
    "video_prompt": ""
  },
  "script_2": {
    "format": "UGC/productshot/testimonial/how-to",
    "hook": "",
    "shots": [
      {
        "tijdstip": "0:00-0:03",
        "beeld": "",
        "camerahoek": "",
        "beweging": "",
        "onscreen_tekst": ""
      }
    ],
    "cta": "",
    "caption_instagram": "",
    "caption_tiktok": "",
    "muziek": "",
    "video_prompt": ""
  }
}
"""

# ============================================================
# HELPERS
# ============================================================

def claude_call(system_prompt, user_message, max_tokens=3000):
    payload = json.dumps({
        "model":      ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "system":     system_prompt,
        "messages":   [{"role": "user", "content": user_message}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload, method="POST"
    )
    req.add_header("x-api-key",         ANTHROPIC_API_KEY)
    req.add_header("anthropic-version",  "2023-06-01")
    req.add_header("Content-Type",       "application/json")

    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode())
            return result["content"][0]["text"]
    except urllib.error.HTTPError as e:
        print(f"[Claude] Fout: {e.code} - {e.read().decode()[:300]}")
        return None


def parse_json(output):
    if not output:
        return {}
    try:
        schone = output.replace("```json", "").replace("```", "")
        start  = schone.find("{")
        einde  = schone.rfind("}") + 1
        if start != -1 and einde > start:
            return json.loads(schone[start:einde])
    except json.JSONDecodeError as e:
        print(f"[JSON] Parse fout: {e}")
    return {}


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


def supabase_post(tabel, data):
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{tabel}",
        data=payload, method="POST"
    )
    req.add_header("apikey",        SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Content-Type",  "application/json")
    req.add_header("Prefer",        "return=representation")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"[Supabase] Post fout: {e.code} - {e.read().decode()[:200]}")
        return None


# ============================================================
# HOOFDFUNCTIES
# ============================================================

def haal_product_op(product_id=None, product_naam=None):
    """Haalt product op uit Supabase inclusief research data."""
    if product_id:
        data = supabase_get("producten", f"select=*&id=eq.{product_id}")
    elif product_naam:
        naam_encoded = urllib.parse.quote(product_naam)
        data = supabase_get("producten", f"select=*&product_naam=eq.{naam_encoded}")
    else:
        data = supabase_get("producten", "select=*&status=eq.Actief&research_gedaan=eq.true&order=id.desc&limit=1")

    if not data:
        print("[Agent 3] Geen product gevonden")
        return None

    product = data[0]
    print(f"[Agent 3] Product geladen: {product.get('product_naam')} (ID: {product.get('id')})")

    # Check of research beschikbaar is
    if not product.get("research_gedaan"):
        print("[Agent 3] Geen research gevonden — eerst Agent 2 uitvoeren")
        return None

    return product


def schrijf_scripts(product):
    """Schrijft 2 video scripts op basis van brand manual en research."""
    print("[Agent 3] Scripts schrijven...")

    brand_manual     = product.get("brand_manual", "")
    hook_bibliotheek = product.get("hook_bibliotheek", []) or []
    cta_bibliotheek  = product.get("cta_bibliotheek", []) or []
    video_ideeen     = []

    research = product.get("research_rapport", {}) or {}
    if isinstance(research, str):
        try:
            research = json.loads(research)
        except:
            research = {}
    video_ideeen = research.get("video_ideeen", [])

    # Haal verboden content en merkarchitectuur op
    brandguide = product.get("brandguide", {}) or {}
    if isinstance(brandguide, str):
        try:
            brandguide = json.loads(brandguide)
        except:
            brandguide = {}
    verboden = brandguide.get("verboden_content", {})

    # Bouw user message
    user_message = (
        "Schrijf 2 video scripts van exact 8 seconden.\n\n"
        "PRODUCT:\n"
        f"Naam: {product.get('product_naam', '')}\n"
        f"USP: {product.get('usp', '')}\n"
        f"Tone: {product.get('tone_of_voice', '')}\n"
        f"Kleuren: {product.get('primaire_kleur', '')} / {product.get('secondaire_kleur', '')}\n"
        f"Soul HEX: {product.get('soul_hex_kleuren', '')}\n"
        f"Vibe: {product.get('vibe_beschrijving', '')}\n\n"
        "BRAND MANUAL (gebruik voor stijl en tone):\n"
        + brand_manual[:2000] + "\n\n"
        "VIDEO IDEEEN UIT RESEARCH:\n"
        + json.dumps(video_ideeen[:3], ensure_ascii=False) + "\n\n"
        "HOOK BIBLIOTHEEK (gebruik deze hooks):\n"
        + json.dumps(hook_bibliotheek[:4], ensure_ascii=False) + "\n\n"
        "CTA BIBLIOTHEEK (gebruik deze CTAs):\n"
        + json.dumps(cta_bibliotheek[:3], ensure_ascii=False) + "\n\n"
        + (f"VERBODEN CONTENT (nooit gebruiken):\n{json.dumps(verboden, ensure_ascii=False)}\n\n" if verboden else "")
        + "Script 1 = hoogste confidence video idee\n"
        "Script 2 = tweede hoogste confidence video idee\n"
        "Return ALLEEN pure JSON."
    )

    # Probeer maximaal 3 keer
    for poging in range(1, 4):
        if poging > 1:
            print(f"[Agent 3] Retry {poging}/3...")
            time.sleep(3)

        output  = claude_call(AGENT_3_PROMPT, user_message, max_tokens=3000)
        scripts = parse_json(output)

        if scripts and scripts.get("script_1") and scripts.get("script_2"):
            print(f"[Agent 3] ✓ 2 scripts geschreven")
            print(f"  Script 1: {scripts['script_1'].get('format', '')} — {scripts['script_1'].get('hook', '')[:50]}")
            print(f"  Script 2: {scripts['script_2'].get('format', '')} — {scripts['script_2'].get('hook', '')[:50]}")
            return scripts

    print("[Agent 3] Script schrijven mislukt na 3 pogingen")
    return None


def sla_scripts_op(product_id, product_naam, scripts):
    """Slaat scripts op in pipeline_runs tabel."""
    print("[Agent 3] Scripts opslaan in Supabase...")

    data = {
        "product_id":   product_id,
        "product_naam": product_naam,
        "video_script": scripts,
        "video_status": "Scripts klaar"
    }

    result = supabase_post("pipeline_runs", data)

    if result:
        run_id = result[0].get("id")
        print(f"[Agent 3] ✓ Scripts opgeslagen — pipeline_run ID: {run_id}")
        return run_id

    print("[Agent 3] ✗ Opslaan mislukt")
    return None


# ============================================================
# HOOFD FUNCTIE
# ============================================================

def run(product_id=None, product_naam=None):
    """Voert Agent 3 uit voor een specifiek product."""
    print("\n" + "=" * 60)
    print("  AGENT 3 — SCRIPT MAKER")
    print("=" * 60)

    # Haal product op
    product = haal_product_op(product_id, product_naam)
    if not product:
        return {"success": False, "bericht": "Product niet gevonden of research ontbreekt"}

    pid  = product.get("id")
    naam = product.get("product_naam", "")

    # Schrijf scripts
    scripts = schrijf_scripts(product)
    if not scripts:
        return {"success": False, "bericht": "Script schrijven mislukt"}

    # Sla op in Supabase
    run_id = sla_scripts_op(pid, naam, scripts)

    print("\n" + "=" * 60)
    print("  AGENT 3 KLAAR")
    print(f"  Product: {naam}")
    print(f"  Pipeline run ID: {run_id}")
    print("  Volgende stap: python agent4.py")
    print("=" * 60)

    return {
        "success":     True,
        "product_id":  pid,
        "run_id":      run_id,
        "scripts":     scripts,
        "bericht":     "Scripts succesvol geschreven"
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 3 — Script Maker")
    parser.add_argument("--product-id",   type=int, help="Supabase product ID")
    parser.add_argument("--product-naam", type=str, help="Product naam")
    args = parser.parse_args()

    resultaat = run(
        product_id=args.product_id,
        product_naam=args.product_naam
    )

    if resultaat.get("scripts"):
        print("\nSCRIPT 1:")
        print(json.dumps(resultaat["scripts"].get("script_1", {}), indent=2, ensure_ascii=False))
        print("\nSCRIPT 2:")
        print(json.dumps(resultaat["scripts"].get("script_2", {}), indent=2, ensure_ascii=False))
