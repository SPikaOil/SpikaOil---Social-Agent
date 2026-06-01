"""
Agent 0 — Brand Manual PDF Reader
Leest een geüploade PDF en extraheert automatisch alle brand info.
Geen interview vragen meer — gewoon een PDF uploaden.

Gebruik:
  python agent0.py --pdf /pad/naar/brand_manual.pdf
  python agent0.py --pdf /pad/naar/brand_manual.pdf --product-url https://...
"""

import urllib.request
import urllib.error
import json
import time
import os
import base64
import sys
import argparse
from datetime import datetime

# ============================================================
# CONFIGURATIE — via config.py
# ============================================================
from config import (
    SUPABASE_URL, SUPABASE_KEY,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    HIGGSFIELD_KEY, HIGGSFIELD_API_ID
)

HIGGSFIELD_AUTH = f"Basic {base64.b64encode(f'{HIGGSFIELD_API_ID}:{HIGGSFIELD_KEY}'.encode()).decode()}"

# ============================================================
# PDF LEZEN
# ============================================================

def lees_pdf(pdf_pad: str) -> str:
    """
    Leest tekst uit een PDF bestand.
    Gebruikt pypdf — installeer via: pip install pypdf
    """
    print(f"[Agent 0] PDF lezen: {pdf_pad}")

    try:
        from pypdf import PdfReader
    except ImportError:
        print("[Agent 0] pypdf niet geïnstalleerd — installeren...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf", "--break-system-packages", "--quiet"])
        from pypdf import PdfReader

    try:
        reader = PdfReader(pdf_pad)
        tekst  = ""

        print(f"[Agent 0] PDF heeft {len(reader.pages)} pagina's")

        for i, page in enumerate(reader.pages):
            pagina_tekst = page.extract_text()
            if pagina_tekst:
                tekst += f"\n--- Pagina {i+1} ---\n{pagina_tekst}"

        if not tekst.strip():
            print("[Agent 0] Geen tekst gevonden in PDF — mogelijk een gescande PDF")
            return ""

        print(f"[Agent 0] ✓ PDF gelezen — {len(tekst)} tekens")
        return tekst

    except Exception as e:
        print(f"[Agent 0] PDF lees fout: {e}")
        return ""


def lees_pdf_van_bytes(pdf_bytes: bytes, bestandsnaam: str = "upload.pdf") -> str:
    """Leest tekst uit PDF bytes (voor uploads via API)."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_pad = tmp.name

    try:
        tekst = lees_pdf(tmp_pad)
        return tekst
    finally:
        os.unlink(tmp_pad)


# ============================================================
# GROQ HELPERS
# ============================================================

def groq_call(system_prompt, user_message, max_tokens=4000, temperature=0.6):
    """Claude API call — vervangt Groq."""
    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_message}
        ]
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


# ============================================================
# BRAND MANUAL GENEREREN UIT PDF
# ============================================================

BRAND_MANUAL_PROMPT = """
Je bent een senior brand strategist met 15+ jaar ervaring.
Je ontvangt de volledige tekst van een brand manual PDF.
Genereer daaruit een gestructureerde, volledige brand manual in Markdown.

Gebruik ALLEEN informatie die in de PDF staat — verzin niets.
Als informatie ontbreekt, geef dat aan met: "[Niet gevonden in PDF]"

Structuur:
# [Merknaam] — Brand Manual [Jaar]

## 1. Merkfundament
### Oorsprong & Missie
### Golden Circle (WHY / HOW / WHAT)
### Merkwaarden
### Merkbelofte
### Merkpersoonlijkheid

## 2. Product & Prijsstrategie
### Productbeschrijving
### Prijspunt & Positionering
### USPs
### Productlijn & Varianten

## 3. Doelgroepen
### Primaire Doelgroep
### Secundaire Doelgroep
### Pijnpunten & Kooptriggers

## 4. Voice & Tone
### De Stem van het Merk
### Tone per Context
### Do's & Don'ts
### Slogansysteem

## 5. Visuele Identiteit
### Kleurenpalet (met hex codes)
### Typografie
### Fotografie & Visuele Stijl
### Logo-systeem

## 6. Concurrentiepositionering
### Competitieflandschap
### Unieke Positionering
### Positioneringsmatrix

## 7. Kanaalgidsen
### Per Platform Strategie
### Content Pijlers
### Format Mix

## Strategische Aanbevelingen
"""

BRAND_DATA_EXTRACT_PROMPT = """
Extraheer gestructureerde data uit deze brand manual tekst.
Return ALLEEN pure JSON — geen markdown, geen backticks.

{
  "product_naam": "",
  "product_beschrijving": "",
  "product_type": "Fysiek product",
  "prijspunt": 0,
  "usp": "",
  "primaire_kleur": "#000000",
  "secondaire_kleur": "#FFFFFF",
  "lettertype": "",
  "visuele_stijl": "",
  "tone_of_voice": "",
  "categorie": "",
  "platform": "Instagram, TikTok",
  "merkbelofte": "",
  "primaire_slogan": "",
  "doelland": "Nederland",
  "doeltaal": "Nederlands",
}

Regels voor extractie:
- primaire_kleur: zoek SPECIFIEK naar de EERSTE merkkleur hex code (#XXXXXX) — NIET #000000 of #FFFFFF tenzij dat letterlijk de merkkleur is
- secondaire_kleur: de TWEEDE merkkleur hex code — NIET #000000 of #FFFFFF tenzij dat letterlijk de merkkleur is
- lettertype: het exacte fontnaam voor headlines/logo (bijv. "Bebas Neue", "Playfair Display")
- visuele_stijl: beschrijf in 1-2 zinnen de visuele sfeer van het merk
- merkbelofte: de merkbelofte zin (vaak tussen aanhalingstekens)
- primaire_slogan: de primaire slogan (vaak tussen aanhalingstekens)

"""

PRODUCT_REFERENCE_PROMPT = """
Je bent een AI video director. Genereer op basis van de brand manual tekst:
1. Product reference prompt voor Higgsfield AI
2. Soul ID persona (primaire doelgroep als AI persona)
3. Editing stijl profiel

Return ALLEEN pure JSON:
{
  "product_reference": {
    "higgsfield_prompt": "",
    "image_reference_url": "",
    "shot_instructie": "",
    "vermijd": []
  },
  "soul_id_persona": {
    "naam": "",
    "leeftijd": "",
    "uiterlijk": "",
    "stijl": "",
    "higgsfield_portret_prompt": ""
  },
  "editing_stijl": {
    "tempo": "",
    "camera_bewegingen": [],
    "cut_stijl": "",
    "belichting": "",
    "kleurgrading": "",
    "muziek_karakter": ""
  }
}
"""

MOODBOARD_PROMPT = """
Je bent een AI art director. Genereer op basis van de brand manual een volledig moodboard pakket.

Return ALLEEN pure JSON:
{
  "product_naam": "",
  "laag_1_prompts": [
    {"nummer": 1, "type": "product close-up", "beschrijving": "", "prompt": ""}
  ],
  "laag_2_soul_hex": {
    "primaire_kleur": "",
    "secondaire_kleur": "",
    "accent_kleur": "",
    "achtergrond_kleur": "",
    "soul_hex_string": ""
  },
  "laag_3_vibe": {
    "algemene_stijl": "",
    "belichting": "",
    "texturen": "",
    "compositie_stijl": "",
    "sfeer_omschrijving": "",
    "master_style_prompt": ""
  }
}

Genereer 10 prompts in laag_1_prompts:
3x product close-up, 2x lifestyle still life, 2x textuur/materiaal,
2x kleur/compositie, 1x ambient mood.
Alle prompts in het Engels.
"""

VERBODEN_CONTENT_PROMPT = """
Extraheer verboden content en merkarchitectuur uit de brand manual.
Return ALLEEN pure JSON:
{
  "verboden_woorden": [],
  "verboden_claims": [],
  "nooit_in_beeld": [],
  "altijd_in_beeld": [],
  "product_presentatie": "",
  "gewenste_emotie": "",
  "ai_masterinstructie": ""
}
"""


# ============================================================
# VERWERKINGS FUNCTIES
# ============================================================

def genereer_brand_manual_uit_pdf(pdf_tekst: str) -> str:
    """Genereert brand manual Markdown uit PDF tekst."""
    print("[Agent 0] Brand manual genereren uit PDF...")

    user_message = (
        "Genereer een volledige brand manual uit deze PDF tekst.\n\n"
        "PDF TEKST:\n" + pdf_tekst[:6000] + "\n\n"
        "Gebruik ALLEEN informatie uit de PDF. Minimaal 1500 woorden."
    )

    manual = groq_call(BRAND_MANUAL_PROMPT, user_message, max_tokens=4000)
    if manual:
        print(f"[Agent 0] ✓ Brand manual gegenereerd ({len(manual)} tekens)")
    return manual


def extraheer_brand_data(pdf_tekst: str) -> dict:
    """Extraheert gestructureerde data direct uit de PDF tekst."""
    print("[Agent 0] Brand data extraheren...")
    time.sleep(5)

    output = groq_call(
        BRAND_DATA_EXTRACT_PROMPT,
        f"Extraheer data uit deze brand manual tekst:\n\n{pdf_tekst[:4000]}",
        max_tokens=800,
        temperature=0.1
    )

    data = parse_json(output)
    if data:
        print(f"[Agent 0] ✓ Brand data geëxtraheerd: {data.get('product_naam', '')}")
    return data


def genereer_product_reference(pdf_tekst: str, brand_data: dict) -> dict:
    """Genereert product reference, Soul ID en editing stijl."""
    print("[Agent 0] Product reference + Soul ID + editing stijl genereren...")
    time.sleep(5)

    user_message = (
        "Genereer product reference, Soul ID en editing stijl.\n\n"
        "BRAND DATA:\n" + json.dumps(brand_data, ensure_ascii=False) + "\n\n"
        "PDF TEKST:\n" + pdf_tekst[:3000]
    )

    output = groq_call(PRODUCT_REFERENCE_PROMPT, user_message, max_tokens=2000, temperature=0.5)
    data   = parse_json(output)
    if data:
        print("[Agent 0] ✓ Product reference gegenereerd")
    return data


def genereer_moodboard(pdf_tekst: str, brand_data: dict) -> dict:
    """Genereert moodboard prompts op basis van PDF tekst — met retry."""
    print("[Agent 0] Moodboard genereren...")
    time.sleep(5)

    user_message = (
        "Genereer moodboard pakket voor dit merk.\n\n"
        "BRAND DATA:\n" + json.dumps(brand_data, ensure_ascii=False) + "\n\n"
        "PDF TEKST:\n" + pdf_tekst[:2000] + "\n\n"
        "BELANGRIJK: Return ALLEEN pure JSON. Geen markdown. Geen backticks. "
        "Zorg dat alle strings correct gesloten zijn met aanhalingstekens."
    )

    # Probeer maximaal 3 keer
    for poging in range(1, 4):
        if poging > 1:
            print(f"[Agent 0] Moodboard retry {poging}/3...")
            time.sleep(3)

        output = groq_call(MOODBOARD_PROMPT, user_message, max_tokens=2000, temperature=0.5)
        data   = parse_json(output)

        if data and data.get("laag_1_prompts"):
            print(f"[Agent 0] ✓ Moodboard gegenereerd ({len(data.get('laag_1_prompts', []))} prompts)")
            return data

    print("[Agent 0] Moodboard generatie mislukt na 3 pogingen — overgeslagen")
    return {}


def genereer_verboden_content(pdf_tekst: str) -> dict:
    """Extraheert verboden content en merkarchitectuur."""
    print("[Agent 0] Verboden content + merkarchitectuur extraheren...")
    time.sleep(5)

    output = groq_call(
        VERBODEN_CONTENT_PROMPT,
        f"Extraheer verboden content en merkarchitectuur:\n\n{pdf_tekst[:3000]}",
        max_tokens=1000,
        temperature=0.1
    )

    data = parse_json(output)
    if data:
        print("[Agent 0] ✓ Verboden content geëxtraheerd")
    return data


def exporteer_markdown(product_naam: str, brand_manual: str) -> str:
    """Slaat brand manual op als .md bestand."""
    veilige_naam = product_naam.lower()
    for t in [' ', '/', '\\', '|', ':', '*', '?', '"', '<', '>']:
        veilige_naam = veilige_naam.replace(t, '_')
    bestandsnaam = f"brand_manual_{veilige_naam}.md"
    with open(bestandsnaam, "w", encoding="utf-8") as f:
        f.write(brand_manual)
    print(f"[Agent 0] Geëxporteerd: {bestandsnaam}")
    return bestandsnaam


def sla_op_in_supabase(brand_data, brand_manual, pdf_tekst,
                        product_url, ref_data=None,
                        moodboard_data=None, verboden_data=None) -> int:
    """Slaat alles op in Supabase."""
    print("\n[Agent 0] Opslaan in Supabase...")

    soul_hex = ""
    vibe     = ""
    if moodboard_data:
        soul_hex = moodboard_data.get("laag_2_soul_hex", {}).get("soul_hex_string", "")
        vibe     = moodboard_data.get("laag_3_vibe", {}).get("master_style_prompt", "")

    # Fallback — gebruik primaire kleuren als soul_hex leeg is
    if not soul_hex and brand_data.get("primaire_kleur"):
        pk = brand_data.get("primaire_kleur", "")
        sk = brand_data.get("secondaire_kleur", "")
        soul_hex = f"{pk}, {sk}" if sk else pk

    record = {
        "product_naam":             brand_data.get("product_naam", ""),
        "product_beschrijving":     brand_data.get("product_beschrijving", ""),
        "product_type":             brand_data.get("product_type", "Fysiek product"),
        "usp":                      brand_data.get("usp", ""),
        "primaire_kleur":           brand_data.get("primaire_kleur", ""),
        "secondaire_kleur":         brand_data.get("secondaire_kleur", ""),
        "lettertype":               brand_data.get("lettertype", ""),
        "visuele_stijl":            brand_data.get("visuele_stijl", ""),
        "tone_of_voice":            brand_data.get("tone_of_voice", ""),
        "categorie":                brand_data.get("categorie", ""),
        "platform":                 brand_data.get("platform", "Instagram, TikTok"),
        "doelland":                 brand_data.get("doelland", "Nederland"),
        "doeltaal":                 brand_data.get("doeltaal", "Nederlands"),
        "product_url":              product_url or "",
        "brand_manual":             brand_manual,
        "brandguide":               {"pdf_tekst": pdf_tekst[:5000]},
        "status":                   "Actief",
        "research_gedaan":          False,
        "moodboard_prompts":        moodboard_data.get("laag_1_prompts") if moodboard_data else None,
        "moodboard_volledig":       moodboard_data if moodboard_data else None,
        "moodboard_status":         "Prompts klaar" if moodboard_data else "Nog niet gegenereerd",
        "soul_hex_kleuren":         soul_hex,
        "vibe_beschrijving":        vibe,
        "product_reference_prompt": ref_data.get("product_reference", {}).get("higgsfield_prompt", "") if ref_data else "",
        "product_image_url":        ref_data.get("product_reference", {}).get("image_reference_url", "") if ref_data else "",
        "soul_id_persona":          ref_data.get("soul_id_persona") if ref_data else None,
        "editing_stijl":            ref_data.get("editing_stijl") if ref_data else None,
        "editing_tempo":            ref_data.get("editing_stijl", {}).get("tempo", "") if ref_data else "",
        "editing_kleurgrading":     ref_data.get("editing_stijl", {}).get("kleurgrading", "") if ref_data else "",
        "muziek_karakter":          ref_data.get("editing_stijl", {}).get("muziek_karakter", "") if ref_data else "",
        "merkbelofte":              brand_data.get("merkbelofte", ""),
        "primaire_slogan":          brand_data.get("primaire_slogan", ""),
    }

    # Voeg verboden content toe als beschikbaar
    if verboden_data:
        record["brandguide"] = {
            "pdf_tekst":        pdf_tekst[:5000],
            "verboden_content": verboden_data
        }

    payload = json.dumps(record).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/producten",
        data=payload, method="POST"
    )
    req.add_header("apikey",        SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Content-Type",  "application/json")
    req.add_header("Prefer",        "return=representation")

    try:
        with urllib.request.urlopen(req) as r:
            result     = json.loads(r.read().decode())
            product_id = result[0].get("id")
            print(f"[Agent 0] ✓ Product opgeslagen — ID: {product_id}")
            return product_id
    except urllib.error.HTTPError as e:
        print(f"[Agent 0] Supabase fout: {e.code} - {e.read().decode()[:300]}")
        return None


# ============================================================
# HOOFD FUNCTIE — AANGEROEPEN DOOR API
# ============================================================

def run_via_api(pdf_bytes: bytes, product_naam: str = "",
                product_url: str = "",
                product_foto: str = "",
                doelland: str = "Nederland", doeltaal: str = "Nederlands") -> dict:
    """
    Wordt aangeroepen vanuit de API met PDF bytes van de upload.
    """
    print("[Agent 0] PDF verwerken via API...")

    # Stap 1 — Lees PDF
    pdf_tekst = lees_pdf_van_bytes(pdf_bytes)
    if not pdf_tekst:
        return {"success": False, "bericht": "Kon geen tekst uit PDF halen — controleer of het geen gescande PDF is"}

    # Stap 2 — Brand data extraheren
    brand_data = extraheer_brand_data(pdf_tekst)
    if doelland:
        brand_data["doelland"] = doelland
    if doeltaal:
        brand_data["doeltaal"] = doeltaal

    # Gebruik meegegeven productnaam als die ingevuld is, anders uit PDF
    product_naam = product_naam.strip() if product_naam and product_naam.strip() else brand_data.get("product_naam", "product")
    brand_data["product_naam"] = product_naam

    # Stap 3 — Brand manual genereren
    brand_manual = genereer_brand_manual_uit_pdf(pdf_tekst)
    if not brand_manual:
        return {"success": False, "bericht": "Fout bij genereren brand manual"}

    # Stap 4 — Exporteer markdown
    exporteer_markdown(product_naam, brand_manual)

    # Stap 5 — Product reference + Soul ID + editing stijl
    ref_data = genereer_product_reference(pdf_tekst, brand_data)

    # Stap 6 — Moodboard
    moodboard_data = genereer_moodboard(pdf_tekst, brand_data)

    # Stap 7 — Verboden content
    verboden_data = genereer_verboden_content(pdf_tekst)

    # Stap 8 — Sla alles op in Supabase
    # Als product_foto meegegeven is overschrijft die de URL uit de PDF
    if product_foto:
        if ref_data:
            ref_data["product_reference"]["image_reference_url"] = product_foto
        brand_data["product_image_url"] = product_foto

    product_id = sla_op_in_supabase(
        brand_data, brand_manual, pdf_tekst,
        product_url, ref_data, moodboard_data, verboden_data
    )

    return {
        "success":      True,
        "product_id":   product_id,
        "product_naam": product_naam,
        "bericht":      f"Brand manual voor {product_naam} succesvol gegenereerd uit PDF."
    }


# ============================================================
# TERMINAL GEBRUIK
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 0 — Brand Manual PDF Reader")
    parser.add_argument("--pdf",         required=True, help="Pad naar de PDF")
    parser.add_argument("--product-url",  default="", help="Product URL (optioneel)")
    parser.add_argument("--product-foto", default="", help="Productfoto URL voor image-to-video")
    parser.add_argument("--doelland",    default="Nederland")
    parser.add_argument("--doeltaal",    default="Nederlands")
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"Fout: PDF niet gevonden: {args.pdf}")
        sys.exit(1)

    with open(args.pdf, "rb") as f:
        pdf_bytes = f.read()

    resultaat = run_via_api(
        pdf_bytes,
        product_url=args.product_url,
        product_foto=getattr(args, "product_foto", ""),
        doelland=args.doelland,
        doeltaal=args.doeltaal
    )

    print(f"\nResultaat: {json.dumps(resultaat, indent=2, ensure_ascii=False)}")
