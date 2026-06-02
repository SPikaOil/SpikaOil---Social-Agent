"""
Agent 2 — Market Research
Voert marktonderzoek uit op basis van de brand manual uit Supabase.
Genereert: video concepten, hook bibliotheek, CTA bibliotheek, video format regels.

Gebruik:
  python agent2.py --product-id 9
  python agent2.py --product-naam "SPika Oil"
"""

import urllib.request
import urllib.error
import json
import time
import os
import sys
import argparse
from config import (
    SUPABASE_URL, SUPABASE_KEY,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL
)

# ============================================================
# SYSTEM PROMPT
# ============================================================

AGENT_2_PROMPT = """
Je bent een social media market research expert voor Instagram Reels en TikTok.
Analyseer de brand manual en genereer marktonderzoek.

KRITIEKE REGELS:
- Return ALLEEN pure JSON — geen markdown, geen backticks, geen uitleg
- Start met { en eindig met }
- Korte en bondige teksten — maximaal 1-2 zinnen per veld
- Geen geneste arrays dieper dan 2 niveaus

Genereer exact dit formaat:
{
  "product_naam": "",
  "doelgroep_primair": "",
  "doelgroep_pijnpunten": ["pijnpunt1", "pijnpunt2", "pijnpunt3"],
  "doelgroep_triggers": ["trigger1", "trigger2", "trigger3"],
  "video_ideeen": [
    {"titel": "", "format": "UGC", "hook": "", "cta": "", "confidence": "hoog"},
    {"titel": "", "format": "productshot", "hook": "", "cta": "", "confidence": "hoog"},
    {"titel": "", "format": "testimonial", "hook": "", "cta": "", "confidence": "medium"},
    {"titel": "", "format": "how-to", "hook": "", "cta": "", "confidence": "medium"},
    {"titel": "", "format": "UGC", "hook": "", "cta": "", "confidence": "medium"}
  ],
  "hook_bibliotheek": [
    {"hook": "", "format": "UGC", "emotie": ""},
    {"hook": "", "format": "productshot", "emotie": ""},
    {"hook": "", "format": "testimonial", "emotie": ""},
    {"hook": "", "format": "how-to", "emotie": ""},
    {"hook": "", "format": "UGC", "emotie": ""},
    {"hook": "", "format": "productshot", "emotie": ""},
    {"hook": "", "format": "UGC", "emotie": ""},
    {"hook": "", "format": "testimonial", "emotie": ""}
  ],
  "cta_bibliotheek": [
    {"cta": "", "platform": "Instagram", "type": "aankoop"},
    {"cta": "", "platform": "TikTok", "type": "aankoop"},
    {"cta": "", "platform": "beide", "type": "volgen"},
    {"cta": "", "platform": "Instagram", "type": "opslaan"},
    {"cta": "", "platform": "TikTok", "type": "delen"},
    {"cta": "", "platform": "beide", "type": "aankoop"}
  ],
  "ugc_dos": ["do1", "do2", "do3"],
  "ugc_donts": ["dont1", "dont2", "dont3"],
  "productshot_dos": ["do1", "do2", "do3"],
  "productshot_donts": ["dont1", "dont2", "dont3"]
}
"""

# ============================================================
# HELPERS
# ============================================================

def claude_call(system_prompt, user_message, max_tokens=4000):
    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload, method="POST"
    )
    req.add_header("x-api-key",        ANTHROPIC_API_KEY)
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("Content-Type",      "application/json")

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
        print(f"[Supabase] Fout: {e.code} - {e.read().decode()[:200]}")
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
        print("[Agent 2] Geen product gevonden in Supabase")
        return None

    product = data[0]
    print(f"[Agent 2] Product geladen: {product.get('product_naam')} (ID: {product.get('id')})")
    return product


def voer_research_uit(product):
    """Voert marktonderzoek uit op basis van brand manual."""
    print("[Agent 2] Market research starten...")

    brand_manual = product.get("brand_manual", "")
    if not brand_manual:
        print("[Agent 2] Geen brand manual gevonden — eerst Agent 0 uitvoeren")
        return None

    # Bouw context op
    product_context = {
        "product_naam":         product.get("product_naam", ""),
        "product_beschrijving": product.get("product_beschrijving", ""),
        "usp":                  product.get("usp", ""),
        "tone_of_voice":        product.get("tone_of_voice", ""),
        "primaire_kleur":       product.get("primaire_kleur", ""),
        "platform":             product.get("platform", "Instagram, TikTok"),
        "doelland":             product.get("doelland", "Nederland"),
        "doeltaal":             product.get("doeltaal", "Nederlands"),
        "categorie":            product.get("categorie", "")
    }

    # Haal verboden content op
    brandguide  = product.get("brandguide", {}) or {}
    if isinstance(brandguide, str):
        try:
            brandguide = json.loads(brandguide)
        except:
            brandguide = {}

    verboden = brandguide.get("verboden_content", {})

    user_message = (
        "Voer marktonderzoek uit voor dit product.\n\n"
        "PRODUCT DATA:\n" + json.dumps(product_context, ensure_ascii=False, indent=2) + "\n\n"
        "BRAND MANUAL:\n" + brand_manual[:4000] + "\n\n"
        + (f"VERBODEN CONTENT (nooit gebruiken):\n{json.dumps(verboden, ensure_ascii=False)}\n\n" if verboden else "")
        + "Platforms: Instagram Reels en TikTok\n"
        "Doel: producten verkopen\n"
        "Return ALLEEN pure JSON."
    )

    # Probeer maximaal 3 keer
    for poging in range(1, 4):
        if poging > 1:
            print(f"[Agent 2] Retry {poging}/3...")
            time.sleep(3)

        output  = claude_call(AGENT_2_PROMPT, user_message, max_tokens=4000)
        rapport = parse_json(output)

        if rapport and (rapport.get("video_ideeen") or rapport.get("hook_bibliotheek")):
            print(f"[Agent 2] ✓ Research rapport gegenereerd")
            print(f"  Video ideeën: {len(rapport.get('video_ideeen', []))}")
            print(f"  Hooks: {len(rapport.get('hook_bibliotheek', []))}")
            print(f"  CTAs: {len(rapport.get('cta_bibliotheek', []))}")
            return rapport

    print("[Agent 2] Research mislukt na 3 pogingen")
    return None


def sla_research_op(product_id, rapport):
    """Slaat research rapport op in Supabase."""
    print("[Agent 2] Research opslaan in Supabase...")

    # Bouw video format regels op uit platte structuur
    video_format_regels = {
        "UGC": {
            "dos":   rapport.get("ugc_dos", []),
            "donts": rapport.get("ugc_donts", [])
        },
        "productshot": {
            "dos":   rapport.get("productshot_dos", []),
            "donts": rapport.get("productshot_donts", [])
        }
    }

    # Bouw hook en CTA bibliotheek op
    hook_bibliotheek = [
        {"hook_tekst": h.get("hook", ""), "format": h.get("format", ""), "emotie": h.get("emotie", "")}
        for h in rapport.get("hook_bibliotheek", [])
    ]

    cta_bibliotheek = [
        {"cta_tekst": c.get("cta", ""), "platform": c.get("platform", ""), "conversie_type": c.get("type", "")}
        for c in rapport.get("cta_bibliotheek", [])
    ]

    data = {
        "research_rapport":    rapport,
        "hook_bibliotheek":    hook_bibliotheek,
        "cta_bibliotheek":     cta_bibliotheek,
        "video_format_regels": video_format_regels,
        "research_gedaan":     True
    }

    succes = supabase_patch("producten", f"id=eq.{product_id}", data)

    if succes:
        print(f"[Agent 2] ✓ Research opgeslagen voor product ID: {product_id}")
    else:
        print("[Agent 2] ✗ Opslaan mislukt")

    return succes


# ============================================================
# HOOFD FUNCTIE
# ============================================================

def run(product_id=None, product_naam=None, project_id=None):
    """
    Voert Agent 2 uit voor een specifiek product of project.
    Als project_id meegegeven wordt, slaat hij research op in projecten tabel.
    """
    import urllib.parse

    print("\n" + "=" * 60)
    print("  AGENT 2 — MARKET RESEARCH")
    print("=" * 60)

    # Haal product op
    product = haal_product_op(product_id, product_naam)
    if not product:
        return {"success": False, "bericht": "Product niet gevonden"}

    pid = product.get("id")

    # Bepaal context — project of product
    if project_id:
        projecten = supabase_get("projecten", f"select=*&id=eq.{project_id}")
        if not projecten:
            return {"success": False, "bericht": f"Project {project_id} niet gevonden"}
        project_data = projecten[0]
        print(f"[Agent 2] Project: {project_data.get('project_naam')} ({project_data.get('doelland')})")

        # Pas product data aan met project taal/land
        product = product.copy()
        product["doelland"] = project_data.get("doelland", product.get("doelland", ""))
        product["doeltaal"] = project_data.get("doeltaal", product.get("doeltaal", ""))
        sla_op_tabel  = "projecten"
        sla_op_filter = f"id=eq.{project_id}"
    else:
        sla_op_tabel  = "producten"
        sla_op_filter = f"id=eq.{pid}"

    # Voer research uit
    rapport = voer_research_uit(product)
    if not rapport:
        return {"success": False, "bericht": "Research mislukt"}

    # Sla op in juiste tabel
    sla_research_op_tabel(sla_op_tabel, sla_op_filter, rapport)

    print("\n" + "=" * 60)
    print("  AGENT 2 KLAAR")
    print(f"  Product: {product.get('product_naam')}")
    if project_id:
        print(f"  Project ID: {project_id}")
    print("  Volgende stap: python agent3.py")
    print("=" * 60)

    return {
        "success":    True,
        "product_id": pid,
        "project_id": project_id,
        "bericht":    "Market research succesvol uitgevoerd",
        "rapport":    rapport
    }


if __name__ == "__main__":
    import urllib.parse

    parser = argparse.ArgumentParser(description="Agent 2 — Market Research")
    parser.add_argument("--product-id",   type=int, help="Supabase product ID")
    parser.add_argument("--product-naam", type=str, help="Product naam")
    parser.add_argument("--force",        action="store_true", help="Opnieuw draaien ook als al gedaan")
    args = parser.parse_args()

    resultaat = run(
        product_id=args.product_id,
        product_naam=args.product_naam
    )

    print(f"\nResultaat: {json.dumps({k: v for k, v in resultaat.items() if k != 'rapport'}, indent=2, ensure_ascii=False)}")
