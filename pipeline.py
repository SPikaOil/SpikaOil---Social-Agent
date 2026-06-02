"""
pipeline.py — Orchestrator met planning
Voert projecten sequentieel uit op basis van project_planning tabel.

Gebruik:
  Handmatig alle geplande projecten vandaag: python pipeline.py
  Specifiek project:                         python pipeline.py --project-id 1
  Nieuw product setup:                       python pipeline.py --nieuw --pdf "brand.pdf"
"""

import json
import time
import os
import sys
import argparse
import urllib.request
import urllib.error
from datetime import datetime, date

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from config import SUPABASE_URL, SUPABASE_KEY

# ============================================================
# HELPERS
# ============================================================

DAGEN_MAP = {
    0: "ma", 1: "di", 2: "wo", 3: "do", 4: "vr", 5: "za", 6: "zo"
}

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
# PLANNING
# ============================================================

def haal_planning_op_voor_vandaag():
    """
    Haalt alle actieve, niet-gepauzeerde planningen op
    die vandaag uitgevoerd moeten worden.
    Gesorteerd op volgorde.
    """
    vandaag_dag = DAGEN_MAP[date.today().weekday()]
    log(f"Vandaag is {vandaag_dag} — planning ophalen...", "info")

    planningen = supabase_get(
        "project_planning",
        "select=*,projecten(id,project_naam,product_id,doelland,doeltaal,status)"
        "&actief=eq.true&gepauzeerd=eq.false&order=volgorde.asc"
    )

    if not planningen:
        return []

    # Filter op dag
    vandaag_planningen = []
    for p in planningen:
        dagen = p.get("dagen", [])
        if vandaag_dag in dagen:
            project = p.get("projecten", {})
            if project and project.get("status") == "Actief":
                vandaag_planningen.append(p)

    log(f"{len(vandaag_planningen)} project(en) gepland voor vandaag", "info")
    return vandaag_planningen


def update_planning_status(planning_id, status):
    """Update de status van een planning regel."""
    data = {
        "laatste_status": status,
        "laatste_run":    date.today().isoformat() if status in ["klaar", "mislukt"] else None
    }
    # Verwijder None waarden
    data = {k: v for k, v in data.items() if v is not None}
    supabase_patch("project_planning", f"id=eq.{planning_id}", data)


# ============================================================
# SETUP NIEUW PRODUCT
# ============================================================

def setup_nieuw_product(pdf_pad, product_naam="", product_url="",
                         product_foto="", doelland="Nederland", doeltaal="Nederlands"):
    log("=" * 55, "header")
    log("SETUP -- NIEUW PRODUCT", "header")
    log("=" * 55, "header")

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
# SETUP NIEUW PROJECT
# ============================================================

def setup_nieuw_project(project_id):
    log("=" * 55, "header")
    log(f"SETUP -- NIEUW PROJECT (ID: {project_id})", "header")
    log("=" * 55, "header")

    projecten = supabase_get("projecten", f"select=*&id=eq.{project_id}")
    if not projecten:
        log(f"Project ID {project_id} niet gevonden", "fout")
        return False

    project      = projecten[0]
    project_naam = project.get("project_naam", "")
    product_id   = project.get("product_id")

    log(f"Project: {project_naam}", "info")

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
    log("=" * 55, "header")
    return True


# ============================================================
# DAGELIJKSE RUN PER PROJECT
# ============================================================

def dagelijkse_run_project(project_id, project_naam=""):
    """Voert de dagelijkse pipeline uit voor één project."""
    log(f"-- Project: {project_naam} (ID: {project_id}) --", "stap")

    # Haal project op
    projecten = supabase_get("projecten", f"select=*&id=eq.{project_id}")
    if not projecten:
        log(f"Project {project_id} niet gevonden", "fout")
        return False

    project    = projecten[0]
    product_id = project.get("product_id")

    # Haal product op voor brand manual
    producten = supabase_get("producten", f"select=*&id=eq.{product_id}")
    if not producten or not producten[0].get("brand_manual"):
        log("Geen brand manual -- eerst product setup uitvoeren", "fout")
        return False

    # Reset research voor trends
    supabase_patch("projecten", f"id=eq.{project_id}", {"research_gedaan": False})

    # Agent 2
    log("Agent 2 -- Market research (trends)...", "stap")
    try:
        import agent2
        res2 = agent2.run(product_id=product_id, project_id=project_id)
        if res2.get("success"):
            log("Agent 2 klaar", "ok")
        else:
            log(f"Agent 2 waarschuwing: {res2.get('bericht')}", "info")
    except Exception as e:
        log(f"Agent 2 fout: {e}", "fout")

    time.sleep(5)

    # Agent 3
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

    # Agent 4
    log("Agent 4 -- Video's genereren...", "stap")
    try:
        import agent4
        res4 = agent4.run(run_id=run_id, product_id=product_id, project_id=project_id)
        if not res4.get("success"):
            log(f"Agent 4 mislukt: {res4.get('bericht')}", "fout")
            return False
        v1 = res4.get("video_url_1", "")
        v2 = res4.get("video_url_2", "")
        log(f"Agent 4 klaar -- V1: {'OK' if v1 else 'Prompt'} | V2: {'OK' if v2 else 'Prompt'}", "ok")
    except Exception as e:
        log(f"Agent 4 fout: {e}", "fout")
        return False

    time.sleep(5)

    # Agent 5
    log("Agent 5 -- Publiceren...", "stap")
    try:
        import agent5
        res5 = agent5.run(run_id=run_id, project_id=project_id)
        if res5.get("success"):
            log("Agent 5 klaar -- Gepubliceerd", "ok")
        else:
            log(f"Agent 5 waarschuwing: {res5.get('bericht')}", "info")
    except ImportError:
        log("Agent 5 overgeslagen", "info")
    except Exception as e:
        log(f"Agent 5 fout: {e}", "fout")

    log(f"OK {project_naam} verwerkt", "ok")
    return True


# ============================================================
# DAGELIJKSE PIPELINE MET PLANNING
# ============================================================

def dagelijkse_pipeline(project_id=None):
    """
    Voert de dagelijkse pipeline uit.
    Als project_id meegegeven: alleen dat project.
    Anders: alle geplande projecten voor vandaag op volgorde.
    """
    log("=" * 55, "header")
    log(f"DAGELIJKSE PIPELINE -- {datetime.now().strftime('%d-%m-%Y %H:%M')}", "header")
    log("=" * 55, "header")

    if project_id:
        # Specifiek project uitvoeren
        projecten = supabase_get("projecten", f"select=*&id=eq.{project_id}")
        if not projecten:
            log(f"Project {project_id} niet gevonden", "fout")
            return

        project      = projecten[0]
        project_naam = project.get("project_naam", "")

        ok = dagelijkse_run_project(project_id, project_naam)
        status = "klaar" if ok else "mislukt"
        log(f"Project {project_naam}: {status}", "ok" if ok else "fout")

    else:
        # Planning ophalen voor vandaag
        planningen = haal_planning_op_voor_vandaag()

        if not planningen:
            log("Geen projecten gepland voor vandaag", "info")
            return

        succes = 0
        for planning in planningen:
            planning_id  = planning.get("id")
            project_data = planning.get("projecten", {})
            pid          = project_data.get("id") if project_data else planning.get("project_id")
            naam         = project_data.get("project_naam", "") if project_data else ""

            # Update status naar draait
            update_planning_status(planning_id, "draait")

            ok = dagelijkse_run_project(pid, naam)

            # Update status na run
            update_planning_status(planning_id, "klaar" if ok else "mislukt")

            if ok:
                succes += 1

            # Wacht even tussen projecten
            time.sleep(5)

        log("=" * 55, "header")
        log(f"PIPELINE KLAAR -- {succes}/{len(planningen)} projecten verwerkt", "ok")
        log("=" * 55, "header")


# ============================================================
# HOOFDPROGRAMMA
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Content Pipeline")
    parser.add_argument("--nieuw",         action="store_true")
    parser.add_argument("--setup-project", action="store_true")
    parser.add_argument("--pdf",           type=str, default="")
    parser.add_argument("--product-naam",  type=str, default="")
    parser.add_argument("--product-url",   type=str, default="")
    parser.add_argument("--product-foto",  type=str, default="")
    parser.add_argument("--product-id",    type=int)
    parser.add_argument("--project-id",    type=int)
    parser.add_argument("--doelland",      type=str, default="Nederland")
    parser.add_argument("--doeltaal",      type=str, default="Nederlands")
    parser.add_argument("--loop",          action="store_true")
    args = parser.parse_args()

    if args.nieuw:
        if not args.pdf:
            print("Fout: --pdf is verplicht")
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
            print("Fout: --project-id is verplicht")
            sys.exit(1)
        setup_nieuw_project(args.project_id)

    elif args.loop:
        while True:
            dagelijkse_pipeline(project_id=args.project_id)
            log("Volgende run over 24 uur...", "info")
            time.sleep(24 * 60 * 60)

    else:
        dagelijkse_pipeline(project_id=args.project_id)
