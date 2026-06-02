"""
pipeline.py — Orchestrator
Ondersteunt zowel producten als projecten.

FLOW PRODUCT (eenmalig):
  Agent 0 -> Brand manual uit PDF
  Agent 1 -> Soul ID aanmaken

FLOW PROJECT (eenmalig):
  Agent 1 -> Soul ID aanmaken voor project
  Agent 2 -> Market research voor project

DAGELIJKS (per project):
  Agent 2 -> Market research (trends)
  Agent 3 -> Scripts schrijven
  Agent 4 -> Video's genereren
  Agent 5 -> Publiceren

Gebruik:
  Nieuw product:   python pipeline.py --nieuw --pdf "brand.pdf"
  Dagelijks:       python pipeline.py
  Per project:     python pipeline.py --project-id 1
"""

import json
import time
import os
import sys
import argparse
import urllib.request
import urllib.error
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from config import SUPABASE_URL, SUPABASE_KEY

# ============================================================
# HELPERS
# ============================================================

def log(tekst, type="info"):
    tijdstip = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "info":   "[ ]",
        "ok":     "[OK]",
        "fout":   "[FOUT]",
        "stap":   "[->]",
        "header": "[=]"
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
        log(f"Supabase patch fout: {e.code}", "fout")
        return False


# ============================================================
# SETUP NIEUW PRODUCT (Agent 0 + Agent 1)
# ============================================================

def setup_nieuw_product(pdf_pad, product_naam="", product_url="", product_foto="", doelland="Nederland", doeltaal="Nederlands"):
    log("=" * 55, "header")
    log("SETUP -- NIEUW PRODUCT", "header")
    log("=" * 55, "header")

    # Agent 0
    log("Agent 0 starten -- Brand manual uit PDF...", "stap")
    try:
        import agent0
        with open(pdf_pad, "rb") as f:
            pdf_bytes = f.read()

        resultaat = agent0.run_via_api(
            pdf_bytes,
            product_naam=product_naam,
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
        log(f"Agent 0 klaar -- {product_naam} (ID: {product_id})", "ok")

    except Exception as e:
        log(f"Agent 0 fout: {e}", "fout")
        return None

    time.sleep(5)

    # Agent 1
    log("Agent 1 starten -- Soul ID aanmaken...", "stap")
    try:
        import agent1
        resultaat_1 = agent1.run(product_id=product_id)
        if resultaat_1.get("success"):
            log(f"Agent 1 klaar -- {resultaat_1.get('soul_id', 'Brand lock opgeslagen')}", "ok")
        else:
            log(f"Agent 1 waarschuwing: {resultaat_1.get('bericht')}", "info")
    except Exception as e:
        log(f"Agent 1 fout: {e}", "fout")

    log("=" * 55, "header")
    log(f"PRODUCT SETUP KLAAR -- {product_naam} (ID: {product_id})", "ok")
    log("Maak nu een project aan via het dashboard.", "info")
    log("=" * 55, "header")

    return product_id


# ============================================================
# SETUP NIEUW PROJECT (Agent 1 + Agent 2)
# ============================================================

def setup_nieuw_project(project_id):
    log("=" * 55, "header")
    log(f"SETUP -- NIEUW PROJECT (ID: {project_id})", "header")
    log("=" * 55, "header")

    # Haal project op
    projecten = supabase_get("projecten", f"select=*&id=eq.{project_id}")
    if not projecten:
        log(f"Project ID {project_id} niet gevonden", "fout")
        return False

    project      = projecten[0]
    project_naam = project.get("project_naam", "")
    product_id   = project.get("product_id")
    doelland     = project.get("doelland", "Nederland")
    doeltaal     = project.get("doeltaal", "Nederlands")

    log(f"Project: {project_naam} ({doelland})", "info")

    # Haal product op voor brand manual
    producten = supabase_get("producten", f"select=*&id=eq.{product_id}")
    if not producten:
        log("Product niet gevonden", "fout")
        return False

    product = producten[0]

    # Agent 1 — Soul ID voor dit project
    log("Agent 1 -- Soul ID aanmaken voor project...", "stap")
    try:
        import agent1
        resultaat_1 = agent1.run(product_id=product_id, project_id=project_id)
        if resultaat_1.get("success"):
            log(f"Agent 1 klaar -- {resultaat_1.get('soul_id', 'Brand lock opgeslagen')}", "ok")
        else:
            log(f"Agent 1 waarschuwing: {resultaat_1.get('bericht')}", "info")
    except Exception as e:
        log(f"Agent 1 fout: {e}", "fout")

    time.sleep(5)

    # Agent 2 — Market research voor dit project
    log("Agent 2 -- Market research voor project...", "stap")
    try:
        import agent2
        resultaat_2 = agent2.run(product_id=product_id, project_id=project_id)
        if resultaat_2.get("success"):
            log("Agent 2 klaar -- Research opgeslagen", "ok")
        else:
            log(f"Agent 2 mislukt: {resultaat_2.get('bericht')}", "fout")
    except Exception as e:
        log(f"Agent 2 fout: {e}", "fout")

    log("=" * 55, "header")
    log(f"PROJECT SETUP KLAAR -- {project_naam}", "ok")
    log("Start dagelijkse pipeline via het dashboard.", "info")
    log("=" * 55, "header")

    return True


# ============================================================
# DAGELIJKSE RUN PER PROJECT
# ============================================================

def dagelijkse_run_project(project):
    project_id   = project.get("id")
    project_naam = project.get("project_naam", "")
    product_id   = project.get("product_id")

    log(f"-- Project: {project_naam} (ID: {project_id}) --", "stap")

    # Haal product op voor brand manual
    producten = supabase_get("producten", f"select=*&id=eq.{product_id}")
    if not producten or not producten[0].get("brand_manual"):
        log("Geen brand manual gevonden -- eerst product setup uitvoeren", "fout")
        return False

    product = producten[0]

    # Reset research zodat Agent 2 altijd opnieuw draait voor trends
    supabase_patch("projecten", f"id=eq.{project_id}", {"research_gedaan": False})

    # Agent 2 — Market research
    log("Agent 2 -- Market research (trends)...", "stap")
    try:
        import agent2
        res2 = agent2.run(product_id=product_id, project_id=project_id)
        if res2.get("success"):
            log("Agent 2 klaar -- Research bijgewerkt", "ok")
        else:
            log(f"Agent 2 waarschuwing: {res2.get('bericht')}", "info")
    except Exception as e:
        log(f"Agent 2 fout: {e}", "fout")

    time.sleep(5)

    # Agent 3 — Scripts schrijven
    log("Agent 3 -- Scripts schrijven...", "stap")
    try:
        import agent3
        res3 = agent3.run(product_id=product_id, project_id=project_id)
        if not res3.get("success"):
            log(f"Agent 3 mislukt: {res3.get('bericht')}", "fout")
            return False
        run_id = res3.get("run_id")
        log(f"Agent 3 klaar -- Run ID: {run_id}", "ok")
    except Exception as e:
        log(f"Agent 3 fout: {e}", "fout")
        return False

    time.sleep(5)

    # Agent 4 — Video's genereren
    log("Agent 4 -- Video's genereren...", "stap")
    try:
        import agent4
        res4 = agent4.run(run_id=run_id, product_id=product_id, project_id=project_id)
        if not res4.get("success"):
            log(f"Agent 4 mislukt: {res4.get('bericht')}", "fout")
            return False
        v1 = res4.get("video_url_1", "")
        v2 = res4.get("video_url_2", "")
        log(f"Agent 4 klaar -- Video 1: {'OK' if v1 else 'Prompt klaar'} | Video 2: {'OK' if v2 else 'Prompt klaar'}", "ok")
    except Exception as e:
        log(f"Agent 4 fout: {e}", "fout")
        return False

    time.sleep(5)

    # Agent 5 — Publiceren
    log("Agent 5 -- Publiceren...", "stap")
    try:
        import agent5
        res5 = agent5.run(run_id=run_id, project_id=project_id)
        if res5.get("success"):
            log("Agent 5 klaar -- Video's ingepland", "ok")
        else:
            log(f"Agent 5 waarschuwing: {res5.get('bericht')}", "info")
    except ImportError:
        log("Agent 5 nog niet beschikbaar -- overgeslagen", "info")
    except Exception as e:
        log(f"Agent 5 fout: {e}", "fout")

    log(f"OK {project_naam} verwerkt", "ok")
    return True


# ============================================================
# DAGELIJKSE PIPELINE
# ============================================================

def dagelijkse_pipeline(product_id=None, project_id=None):
    log("=" * 55, "header")
    log(f"DAGELIJKSE PIPELINE -- {datetime.now().strftime('%d-%m-%Y %H:%M')}", "header")
    log("=" * 55, "header")

    # Specifiek project
    if project_id:
        projecten = supabase_get("projecten", f"select=*&id=eq.{project_id}")
    elif product_id:
        projecten = supabase_get("projecten", f"select=*&product_id=eq.{product_id}&status=eq.Actief")
    else:
        projecten = supabase_get("projecten", "select=*&status=eq.Actief&order=id.asc")

    if not projecten:
        log("Geen actieve projecten gevonden", "fout")
        return

    log(f"{len(projecten)} actief project(en) gevonden", "info")

    succes = 0
    for project in projecten:
        ok = dagelijkse_run_project(project)
        if ok:
            succes += 1
        time.sleep(3)

    log("=" * 55, "header")
    log(f"PIPELINE KLAAR -- {succes}/{len(projecten)} projecten verwerkt", "ok")
    log("=" * 55, "header")


# ============================================================
# HOOFDPROGRAMMA
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Content Pipeline Orchestrator")
    parser.add_argument("--nieuw",        action="store_true", help="Nieuw product toevoegen")
    parser.add_argument("--pdf",          type=str,            help="Pad naar brand manual PDF")
    parser.add_argument("--product-naam", type=str, default="", help="Productnaam")
    parser.add_argument("--product-url",  type=str, default="", help="Product URL")
    parser.add_argument("--product-foto", type=str, default="", help="Productfoto URL")
    parser.add_argument("--product-id",   type=int,            help="Supabase product ID")
    parser.add_argument("--project-id",   type=int,            help="Supabase project ID")
    parser.add_argument("--setup-project",action="store_true", help="Setup nieuw project")
    parser.add_argument("--doelland",     type=str, default="Nederland")
    parser.add_argument("--doeltaal",     type=str, default="Nederlands")
    parser.add_argument("--loop",         action="store_true", help="Blijf elke 24u draaien")
    args = parser.parse_args()

    if args.nieuw:
        if not args.pdf:
            print("Fout: --pdf is verplicht bij --nieuw")
            sys.exit(1)
        setup_nieuw_product(
            pdf_pad=args.pdf,
            product_naam=args.product_naam,
            product_url=args.product_url,
            product_foto=args.product_foto,
            doelland=args.doelland,
            doeltaal=args.doeltaal
        )

    elif args.setup_project:
        if not args.project_id:
            print("Fout: --project-id is verplicht bij --setup-project")
            sys.exit(1)
        setup_nieuw_project(args.project_id)

    elif args.loop:
        while True:
            dagelijkse_pipeline(product_id=args.product_id, project_id=args.project_id)
            log("Volgende run over 24 uur...", "info")
            time.sleep(24 * 60 * 60)

    else:
        dagelijkse_pipeline(product_id=args.product_id, project_id=args.project_id)
