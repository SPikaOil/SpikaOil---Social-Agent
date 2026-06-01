"""
pipeline.py — Orchestrator
Koppelt alle agents en voert de volledige pipeline uit.

FLOW:
  Eenmalig per product:
    Agent 0 -> Brand manual uit PDF
    Agent 1 -> Soul ID aanmaken
    Agent 2 -> Market research

  Dagelijks per actief product:
    Agent 3 -> Scripts schrijven
    Agent 4 -> Video's genereren
    Agent 5 -> Publiceren
    Agent 6 -> Performance analyse (na 24-48u)

Gebruik:
  Nieuw product:       python pipeline.py --nieuw --pdf "brand.pdf" --product-url "https://..."
  Dagelijkse run:      python pipeline.py
  Specifiek product:   python pipeline.py --product-id 14
  Alleen setup:        python pipeline.py --setup --product-id 14
"""

import json
import time
import os
import sys
import argparse
import urllib.request
import urllib.error
from datetime import datetime

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from config import SUPABASE_URL, SUPABASE_KEY

# ============================================================
# HELPERS
# ============================================================

def log(tekst, type="info"):
    tijdstip = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "info":    "[ ]",
        "ok":      "[OK]",
        "fout":    "[FOUT]",
        "stap":    "[->]",
        "header":  "[=]"
    }.get(type, "[ ]")
    print(f"{tijdstip} {prefix} {tekst}")


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
        log(f"Supabase fout: {e.code}", "fout")
        return []


def haal_actieve_producten_op():
    """Haalt alle actieve producten op uit Supabase."""
    return supabase_get(
        "producten",
        "select=id,product_naam,status,research_gedaan,soul_id,brand_manual&status=eq.Actief&order=id.asc"
    )


# ============================================================
# SETUP FLOW (eenmalig per product)
# ============================================================

def setup_nieuw_product(pdf_pad, product_url="", product_foto="", doelland="Nederland", doeltaal="Nederlands"):
    """
    Volledige setup voor een nieuw product.
    Voert Agent 0 -> Agent 1 -> Agent 2 uit.
    """
    log("=" * 55, "header")
    log("SETUP — NIEUW PRODUCT", "header")
    log("=" * 55, "header")

    # -- Agent 0 — Brand manual uit PDF --
    log("Agent 0 starten — Brand manual uit PDF...", "stap")
    try:
        import agent0
        with open(pdf_pad, "rb") as f:
            pdf_bytes = f.read()

        resultaat = agent0.run_via_api(
            pdf_bytes,
            product_url=product_url,
            product_foto=product_foto,
            doelland=doelland,
            doeltaal=doeltaal
        )

        if not resultaat.get("success"):
            log(f"Agent 0 mislukt: {resultaat.get('bericht')}", "fout")
            return None

        product_id   = resultaat.get("product_id")
        product_naam = resultaat.get("product_naam")
        log(f"Agent 0 klaar — {product_naam} (ID: {product_id})", "ok")

    except Exception as e:
        log(f"Agent 0 fout: {e}", "fout")
        return None

    time.sleep(5)

    # -- Agent 1 — Soul ID aanmaken --
    log("Agent 1 starten — Soul ID aanmaken...", "stap")
    try:
        import agent1
        resultaat_1 = agent1.run(product_id=product_id)
        if resultaat_1.get("success"):
            log(f"Agent 1 klaar — Soul ID: {resultaat_1.get('soul_id', 'Brand lock opgeslagen')}", "ok")
        else:
            log(f"Agent 1 waarschuwing: {resultaat_1.get('bericht')}", "info")
    except Exception as e:
        log(f"Agent 1 fout: {e}", "fout")

    time.sleep(5)

    # -- Agent 2 — Market research --
    log("Agent 2 starten — Market research...", "stap")
    try:
        import agent2
        resultaat_2 = agent2.run(product_id=product_id)
        if resultaat_2.get("success"):
            log("Agent 2 klaar — Research opgeslagen", "ok")
        else:
            log(f"Agent 2 mislukt: {resultaat_2.get('bericht')}", "fout")
    except Exception as e:
        log(f"Agent 2 fout: {e}", "fout")

    log("=" * 55, "header")
    log(f"SETUP KLAAR — {product_naam} (ID: {product_id})", "ok")
    log("Start dagelijkse pipeline: python pipeline.py", "info")
    log("=" * 55, "header")

    return product_id


# ============================================================
# DAGELIJKSE FLOW
# ============================================================

def dagelijkse_run_product(product):
    """
    Dagelijkse pipeline voor één product.
    Voert Agent 3 -> Agent 4 -> Agent 5 uit.
    """
    product_id   = product.get("id")
    product_naam = product.get("product_naam", "")

    log(f"-- {product_naam} (ID: {product_id}) --", "stap")

    # Check of setup compleet is
    if not product.get("brand_manual"):
        log(f"Geen brand manual — eerst setup uitvoeren: python pipeline.py --setup --product-id {product_id}", "fout")
        return False

    if not product.get("research_gedaan"):
        log("Research niet gedaan — Agent 2 uitvoeren...", "info")
        try:
            import agent2
            agent2.run(product_id=product_id)
        except Exception as e:
            log(f"Agent 2 fout: {e}", "fout")
            return False
        time.sleep(5)

    # -- Agent 3 — Scripts schrijven --
    log("Agent 3 — Scripts schrijven...", "stap")
    try:
        import agent3
        resultaat_3 = agent3.run(product_id=product_id)
        if not resultaat_3.get("success"):
            log(f"Agent 3 mislukt: {resultaat_3.get('bericht')}", "fout")
            return False
        run_id = resultaat_3.get("run_id")
        log(f"Agent 3 klaar — Pipeline run ID: {run_id}", "ok")
    except Exception as e:
        log(f"Agent 3 fout: {e}", "fout")
        return False

    time.sleep(5)

    # -- Agent 4 — Video's genereren --
    log("Agent 4 — Video's genereren...", "stap")
    try:
        import agent4
        resultaat_4 = agent4.run(run_id=run_id, product_id=product_id)
        if not resultaat_4.get("success"):
            log(f"Agent 4 mislukt: {resultaat_4.get('bericht')}", "fout")
            return False

        v1 = resultaat_4.get("video_url_1", "")
        v2 = resultaat_4.get("video_url_2", "")
        log(f"Agent 4 klaar — Video 1: {'OK' if v1 else 'Prompt klaar'} | Video 2: {'OK' if v2 else 'Prompt klaar'}", "ok")
    except Exception as e:
        log(f"Agent 4 fout: {e}", "fout")
        return False

    time.sleep(5)

    # -- Agent 5 — Publiceren --
    log("Agent 5 — Publiceren...", "stap")
    try:
        import agent5
        resultaat_5 = agent5.run(run_id=run_id, product_id=product_id)
        if resultaat_5.get("success"):
            log("Agent 5 klaar — Video's ingepland voor publicatie", "ok")
        else:
            log(f"Agent 5 waarschuwing: {resultaat_5.get('bericht')}", "info")
    except ImportError:
        log("Agent 5 nog niet beschikbaar — overgeslagen", "info")
    except Exception as e:
        log(f"Agent 5 fout: {e}", "fout")

    log(f"OK {product_naam} verwerkt", "ok")
    return True


def dagelijkse_pipeline(product_id=None):
    """
    Dagelijkse pipeline voor alle actieve producten of één specifiek product.
    """
    log("=" * 55, "header")
    log(f"DAGELIJKSE PIPELINE — {datetime.now().strftime('%d-%m-%Y %H:%M')}", "header")
    log("=" * 55, "header")

    # Haal producten op
    if product_id:
        producten = supabase_get("producten", f"select=*&id=eq.{product_id}")
    else:
        producten = haal_actieve_producten_op()

    if not producten:
        log("Geen actieve producten gevonden", "fout")
        return

    log(f"{len(producten)} actief product(en) gevonden", "info")

    succes = 0
    for product in producten:
        ok = dagelijkse_run_product(product)
        if ok:
            succes += 1
        time.sleep(3)

    log("=" * 55, "header")
    log(f"PIPELINE KLAAR — {succes}/{len(producten)} producten verwerkt", "ok")
    log("=" * 55, "header")


# ============================================================
# SETUP FLOW VOOR BESTAAND PRODUCT
# ============================================================

def setup_bestaand_product(product_id):
    """
    Voert setup stappen uit voor een bestaand product in Supabase.
    Handig als Agent 1 of 2 opnieuw nodig is.
    """
    log("=" * 55, "header")
    log(f"SETUP — BESTAAND PRODUCT (ID: {product_id})", "header")
    log("=" * 55, "header")

    producten = supabase_get("producten", f"select=*&id=eq.{product_id}")
    if not producten:
        log(f"Product ID {product_id} niet gevonden", "fout")
        return

    product      = producten[0]
    product_naam = product.get("product_naam", "")
    log(f"Product: {product_naam}", "info")

    # Agent 1 — Soul ID
    if not product.get("soul_id"):
        log("Agent 1 — Soul ID aanmaken...", "stap")
        try:
            import agent1
            resultaat = agent1.run(product_id=product_id)
            if resultaat.get("success"):
                log(f"Agent 1 klaar", "ok")
        except Exception as e:
            log(f"Agent 1 fout: {e}", "fout")
        time.sleep(5)
    else:
        log(f"Soul ID al aangemaakt: {product.get('soul_id')}", "ok")

    # Agent 2 — Research
    if not product.get("research_gedaan"):
        log("Agent 2 — Market research...", "stap")
        try:
            import agent2
            resultaat = agent2.run(product_id=product_id)
            if resultaat.get("success"):
                log("Agent 2 klaar", "ok")
        except Exception as e:
            log(f"Agent 2 fout: {e}", "fout")
    else:
        log("Research al gedaan", "ok")

    log("=" * 55, "header")
    log(f"SETUP KLAAR — {product_naam}", "ok")
    log("=" * 55, "header")


# ============================================================
# HOOFDPROGRAMMA
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Content Pipeline Orchestrator")
    parser.add_argument("--nieuw",       action="store_true", help="Nieuw product toevoegen")
    parser.add_argument("--setup",       action="store_true", help="Setup voor bestaand product")
    parser.add_argument("--pdf",         type=str,            help="Pad naar brand manual PDF")
    parser.add_argument("--product-url",  type=str, default="", help="Product URL")
    parser.add_argument("--product-foto", type=str, default="", help="Productfoto URL voor image-to-video")
    parser.add_argument("--product-id",   type=int,            help="Supabase product ID")
    parser.add_argument("--doelland",    type=str, default="Nederland")
    parser.add_argument("--doeltaal",    type=str, default="Nederlands")
    parser.add_argument("--loop",           action="store_true", help="Blijf elke 24u draaien")
    parser.add_argument("--force-research", action="store_true", help="Agent 2 opnieuw draaien ook als al gedaan")
    args = parser.parse_args()

    if args.nieuw:
        # Nieuw product toevoegen
        if not args.pdf:
            print("Fout: --pdf is verplicht bij --nieuw")
            sys.exit(1)
        if not os.path.exists(args.pdf):
            print(f"Fout: PDF niet gevonden: {args.pdf}")
            sys.exit(1)

        setup_nieuw_product(
            pdf_pad=args.pdf,
            product_url=args.product_url,
            product_foto=args.product_foto,
            doelland=args.doelland,
            doeltaal=args.doeltaal
        )

    elif args.setup:
        # Setup voor bestaand product
        if not args.product_id:
            print("Fout: --product-id is verplicht bij --setup")
            sys.exit(1)
        setup_bestaand_product(args.product_id)

    elif args.loop:
        # Oneindige loop — voor VPS gebruik
        while True:
            dagelijkse_pipeline(product_id=args.product_id)
            log("Volgende run over 24 uur...", "info")
            time.sleep(24 * 60 * 60)

    else:
        # Eenmalige dagelijkse run
        dagelijkse_pipeline(product_id=args.product_id)
