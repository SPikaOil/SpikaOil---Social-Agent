"""
api.py - FastAPI backend
Draait op http://162.55.215.56:8000
Start met: python -m uvicorn api:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import subprocess
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SUPABASE_URL, SUPABASE_KEY

app = FastAPI(title="AI Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# STATE
# ============================================================

state = {
    "draait":        False,
    "huidige_agent": None,
    "logs":          [],
    "laatste_run":   None,
    "proces":        None
}


def log(tekst, type="dim"):
    tijdstip = datetime.now().strftime("%H:%M:%S")
    state["logs"].append({"tijd": tijdstip, "tekst": tekst, "type": type})
    if len(state["logs"]) > 500:
        state["logs"] = state["logs"][-500:]
    print(f"[{tijdstip}] {tekst}")


# ============================================================
# SUPABASE
# ============================================================

def supabase_get(tabel, filter=""):
    url = f"{SUPABASE_URL}/rest/v1/{tabel}"
    if filter:
        url += f"?{filter}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


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
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# PIPELINE RUNNERS
# ============================================================

def run_setup_taak(pdf_bytes, product_naam, product_url, product_foto, doelland, doeltaal):
    """Setup nieuw product: Agent 0 -> Agent 1"""
    state["draait"]      = True
    state["laatste_run"] = datetime.now().strftime("%d-%m-%Y %H:%M")
    state["logs"]        = []

    log("Setup nieuw product gestart", "gold")
    log("Agent 0 -> Agent 1", "dim")

    try:
        import time
        import agent0

        state["huidige_agent"] = 0
        log("Agent 0 - Brand manual genereren uit PDF...", "amber")

        resultaat = agent0.run_via_api(
            pdf_bytes,
            product_naam=product_naam,
            product_url=product_url,
            product_foto=product_foto,
            doelland=doelland,
            doeltaal=doeltaal
        )

        if not resultaat.get("success"):
            log(f"Agent 0 mislukt: {resultaat.get('bericht')}", "red")
            return

        product_id   = resultaat.get("product_id")
        product_naam_uit = resultaat.get("product_naam")
        log(f"Agent 0 klaar - {product_naam_uit} (ID: {product_id})", "green")

        time.sleep(3)

        state["huidige_agent"] = 1
        log("Agent 1 - Soul ID aanmaken...", "amber")

        try:
            import agent1
            resultaat_1 = agent1.run(product_id=product_id)
            if resultaat_1.get("success"):
                log(f"Agent 1 klaar - {resultaat_1.get('soul_id', 'Brand lock opgeslagen')}", "green")
            else:
                log(f"Agent 1 waarschuwing: {resultaat_1.get('bericht')}", "amber")
        except Exception as e:
            log(f"Agent 1 fout: {str(e)}", "red")

        log("Product setup klaar! Maak nu een project aan.", "gold")

    except Exception as e:
        log(f"Setup fout: {str(e)}", "red")
    finally:
        state["draait"]        = False
        state["huidige_agent"] = None


def run_setup_project_taak(project_id):
    """Setup nieuw project: Agent 1 -> Agent 2"""
    state["draait"]      = True
    state["laatste_run"] = datetime.now().strftime("%d-%m-%Y %H:%M")
    state["logs"]        = []

    log("Setup nieuw project gestart", "gold")
    log("Agent 1 -> Agent 2", "dim")

    try:
        import time
        import agent1
        import agent2

        state["huidige_agent"] = 1
        log("Agent 1 - Soul ID aanmaken voor project...", "amber")

        resultaat_1 = agent1.run(project_id=project_id)
        if resultaat_1.get("success"):
            log(f"Agent 1 klaar - {resultaat_1.get('soul_id', 'Brand lock opgeslagen')}", "green")
        else:
            log(f"Agent 1 waarschuwing: {resultaat_1.get('bericht')}", "amber")

        time.sleep(3)

        state["huidige_agent"] = 2
        log("Agent 2 - Market research voor project...", "amber")

        # Haal product_id op van project
        projecten = supabase_get("projecten", f"select=product_id&id=eq.{project_id}")
        product_id = projecten[0].get("product_id") if projecten and isinstance(projecten, list) else None

        resultaat_2 = agent2.run(product_id=product_id, project_id=project_id)
        if resultaat_2.get("success"):
            log("Agent 2 klaar - Research opgeslagen", "green")
        else:
            log(f"Agent 2 mislukt: {resultaat_2.get('bericht')}", "red")

        log("Project setup klaar! Start de dagelijkse pipeline.", "gold")

    except Exception as e:
        log(f"Project setup fout: {str(e)}", "red")
    finally:
        state["draait"]        = False
        state["huidige_agent"] = None


def run_pipeline_taak(product_id=None, project_id=None):
    """Dagelijkse pipeline: Agent 2 -> 3 -> 4 -> 5"""
    state["draait"]      = True
    state["laatste_run"] = datetime.now().strftime("%d-%m-%Y %H:%M")
    state["logs"]        = []

    log("Dagelijkse pipeline gestart", "gold")

    try:
        cmd = [sys.executable, "pipeline.py"]
        if project_id:
            cmd += ["--project-id", str(project_id)]
        elif product_id:
            cmd += ["--product-id", str(product_id)]

        proces = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        state["proces"] = proces

        for regel in proces.stdout:
            regel = regel.strip()
            if not regel:
                continue

            if "OK" in regel or "KLAAR" in regel:
                type = "green"
            elif "FOUT" in regel or "fout" in regel.lower() or "mislukt" in regel.lower():
                type = "red"
            elif "Agent" in regel:
                type = "amber"
            elif "PIPELINE" in regel or "===" in regel:
                type = "gold"
            else:
                type = "dim"

            log(regel, type)

            for num in ["0", "1", "2", "3", "4", "5", "6"]:
                if f"Agent {num}" in regel:
                    state["huidige_agent"] = int(num)

        proces.wait()
        log("Pipeline afgerond", "green" if proces.returncode == 0 else "red")

    except Exception as e:
        log(f"Pipeline fout: {str(e)}", "red")
    finally:
        state["draait"]        = False
        state["huidige_agent"] = None
        state["proces"]        = None


# ============================================================
# BASIS ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {"status": "AI Pipeline API draait", "versie": "3.0", "draait": state["draait"]}


@app.get("/dashboard")
async def dashboard():
    for naam in ["dashboard.html", "ai-pipeline-dashboard.html"]:
        pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), naam)
        if os.path.exists(pad):
            return FileResponse(pad)
    return JSONResponse({"error": "dashboard.html niet gevonden"}, status_code=404)


@app.get("/status")
def get_status():
    return {
        "draait":        state["draait"],
        "huidige_agent": state["huidige_agent"],
        "laatste_run":   state["laatste_run"],
        "log_count":     len(state["logs"])
    }


@app.get("/logs")
def get_logs():
    return {"logs": state["logs"][-100:]}


@app.delete("/logs")
def clear_logs():
    state["logs"] = []
    return {"success": True}


# ============================================================
# PRODUCT ENDPOINTS
# ============================================================

@app.get("/producten")
def get_producten():
    data = supabase_get("producten", "select=id,product_naam,status,categorie,primaire_kleur&order=id.desc")
    return {"producten": data}


@app.post("/agent0/upload-pdf")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    pdf:          UploadFile = File(...),
    product_naam: str = Form(default=""),
    product_url:  str = Form(default=""),
    product_foto: str = Form(default=""),
    doelland:     str = Form(default="Nederland"),
    doeltaal:     str = Form(default="Nederlands")
):
    """Upload PDF en start product setup: Agent 0 -> Agent 1"""
    if state["draait"]:
        return {"success": False, "bericht": "Pipeline draait al"}
    if not pdf.filename.lower().endswith(".pdf"):
        return {"success": False, "bericht": "Alleen PDF bestanden zijn toegestaan"}

    pdf_bytes = await pdf.read()
    if len(pdf_bytes) == 0:
        return {"success": False, "bericht": "PDF bestand is leeg"}

    log(f"PDF ontvangen: {pdf.filename}", "gold")
    background_tasks.add_task(run_setup_taak, pdf_bytes, product_naam, product_url, product_foto, doelland, doeltaal)
    return {"success": True, "bericht": f"Setup gestart voor {pdf.filename}"}


# ============================================================
# PROJECT ENDPOINTS
# ============================================================

@app.get("/projecten")
def get_projecten():
    """Alle projecten ophalen met product naam."""
    data = supabase_get("projecten", "select=id,project_naam,product_id,doelland,doeltaal,instagram_account,tiktok_account,status,soul_id&order=id.desc")
    return {"projecten": data}


@app.get("/projecten/product/{product_id}")
def get_projecten_van_product(product_id: int):
    """Projecten van een specifiek product ophalen."""
    data = supabase_get("projecten", f"select=*&product_id=eq.{product_id}&order=id.desc")
    return {"projecten": data}


class NieuwProjectData(BaseModel):
    product_id:        int
    project_naam:      str
    doelland:          str = "Nederland"
    doeltaal:          str = "Nederlands"
    instagram_account: Optional[str] = ""
    tiktok_account:    Optional[str] = ""


@app.post("/projecten/nieuw")
def nieuw_project(data: NieuwProjectData, background_tasks: BackgroundTasks):
    """Maak een nieuw project aan en start setup: Agent 1 -> Agent 2"""
    if state["draait"]:
        return {"success": False, "bericht": "Pipeline draait al"}

    # Maak project aan in Supabase
    project_data = {
        "product_id":        data.product_id,
        "project_naam":      data.project_naam,
        "doelland":          data.doelland,
        "doeltaal":          data.doeltaal,
        "instagram_account": data.instagram_account,
        "tiktok_account":    data.tiktok_account,
        "status":            "Actief"
    }

    result = supabase_post("projecten", project_data)
    if not result or isinstance(result, dict) and result.get("error"):
        return {"success": False, "bericht": f"Project aanmaken mislukt: {result}"}

    project_id = result[0].get("id")
    log(f"Project aangemaakt: {data.project_naam} (ID: {project_id})", "gold")

    # Start setup op achtergrond
    background_tasks.add_task(run_setup_project_taak, project_id)

    return {
        "success":    True,
        "project_id": project_id,
        "bericht":    f"Project {data.project_naam} aangemaakt — setup gestart"
    }


# ============================================================
# PIPELINE ENDPOINTS
# ============================================================

class PipelineStart(BaseModel):
    product_id: Optional[int] = None
    project_id: Optional[int] = None


@app.post("/pipeline/starten")
def start_pipeline(data: PipelineStart, background_tasks: BackgroundTasks):
    if state["draait"]:
        return {"success": False, "bericht": "Pipeline draait al"}
    background_tasks.add_task(run_pipeline_taak, data.product_id, data.project_id)
    return {"success": True, "bericht": "Pipeline gestart"}


@app.post("/pipeline/stoppen")
def stop_pipeline():
    if state["proces"]:
        state["proces"].terminate()
        log("Pipeline gestopt door gebruiker", "amber")
    state["draait"]        = False
    state["huidige_agent"] = None
    return {"success": True, "bericht": "Pipeline gestopt"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ============================================================
# PLANNING ENDPOINTS
# ============================================================

@app.get("/planning")
def get_planning():
    """Haalt alle planningen op gesorteerd op volgorde."""
    data = supabase_get(
        "project_planning",
        "select=*,projecten(id,project_naam,doelland,doeltaal,status)&order=volgorde.asc"
    )
    return {"planning": data}


class PlanningData(BaseModel):
    project_id: int
    volgorde:   int = 1
    actief:     bool = True
    gepauzeerd: bool = False
    dagen:      list = ["ma", "di", "wo", "do", "vr", "za", "zo"]


@app.post("/planning/nieuw")
def nieuw_planning(data: PlanningData):
    """Voegt een project toe aan de planning."""
    record = {
        "project_id": data.project_id,
        "volgorde":   data.volgorde,
        "actief":     data.actief,
        "gepauzeerd": data.gepauzeerd,
        "dagen":      data.dagen
    }
    result = supabase_post("project_planning", record)
    if not result or isinstance(result, dict) and result.get("error"):
        return {"success": False, "bericht": f"Mislukt: {result}"}
    return {"success": True, "planning_id": result[0].get("id"), "bericht": "Planning aangemaakt"}


class PlanningUpdate(BaseModel):
    volgorde:   int  = None
    actief:     bool = None
    gepauzeerd: bool = None
    dagen:      list = None


@app.patch("/planning/{planning_id}")
def update_planning(planning_id: int, data: PlanningUpdate):
    """Update een planning regel."""
    update = {k: v for k, v in data.dict().items() if v is not None}
    if not update:
        return {"success": False, "bericht": "Geen wijzigingen"}

    payload = json.dumps(update).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/project_planning?id=eq.{planning_id}",
        data=payload, method="PATCH"
    )
    req.add_header("apikey",        SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Content-Type",  "application/json")
    try:
        with urllib.request.urlopen(req):
            return {"success": True, "bericht": "Planning bijgewerkt"}
    except Exception as e:
        return {"success": False, "bericht": str(e)}


@app.delete("/planning/{planning_id}")
def verwijder_planning(planning_id: int):
    """Verwijdert een planning regel."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/project_planning?id=eq.{planning_id}",
        method="DELETE"
    )
    req.add_header("apikey",        SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    try:
        with urllib.request.urlopen(req):
            return {"success": True, "bericht": "Planning verwijderd"}
    except Exception as e:
        return {"success": False, "bericht": str(e)}


@app.post("/planning/pauzeer/{planning_id}")
def pauzeer_planning(planning_id: int):
    """Pauzeert een planning."""
    payload = json.dumps({"gepauzeerd": True}).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/project_planning?id=eq.{planning_id}",
        data=payload, method="PATCH"
    )
    req.add_header("apikey",        SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Content-Type",  "application/json")
    try:
        with urllib.request.urlopen(req):
            return {"success": True, "bericht": "Planning gepauzeerd"}
    except Exception as e:
        return {"success": False, "bericht": str(e)}


@app.post("/planning/hervat/{planning_id}")
def hervat_planning(planning_id: int):
    """Hervatten van een gepauzeerde planning."""
    payload = json.dumps({"gepauzeerd": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/project_planning?id=eq.{planning_id}",
        data=payload, method="PATCH"
    )
    req.add_header("apikey",        SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Content-Type",  "application/json")
    try:
        with urllib.request.urlopen(req):
            return {"success": True, "bericht": "Planning hervat"}
    except Exception as e:
        return {"success": False, "bericht": str(e)}
