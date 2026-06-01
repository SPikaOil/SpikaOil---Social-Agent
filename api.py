"""
api.py - Lokale FastAPI backend
Draait op localhost:8000
Start met: python -m uvicorn api:app --reload
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


# ============================================================
# PIPELINE RUNNER
# ============================================================

def run_pipeline_taak(product_id=None):
    """Voert dagelijkse pipeline uit als background taak."""
    state["draait"]      = True
    state["laatste_run"] = datetime.now().strftime("%d-%m-%Y %H:%M")
    state["logs"]        = []

    log("Pipeline gestart", "gold")

    try:
        cmd = [sys.executable, "pipeline.py"]
        if product_id:
            cmd += ["--product-id", str(product_id)]
        # Agent 2 wordt elke run opnieuw uitgevoerd voor trends
        cmd += ["--force-research"]

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

        if proces.returncode == 0:
            log("Pipeline succesvol afgerond", "green")
        else:
            log(f"Pipeline gestopt met code {proces.returncode}", "red")

    except Exception as e:
        log(f"Pipeline fout: {str(e)}", "red")
    finally:
        state["draait"]        = False
        state["huidige_agent"] = None
        state["proces"]        = None


def run_setup_taak(pdf_bytes, product_naam, product_url, product_foto, doelland, doeltaal):
    """
    Voert volledige setup uit voor nieuw product:
    Agent 0 -> Agent 1 -> Agent 2
    """
    import time

    state["draait"]      = True
    state["laatste_run"] = datetime.now().strftime("%d-%m-%Y %H:%M")
    state["logs"]        = []

    log("Setup nieuw product gestart", "gold")
    log("Agent 0 -> Agent 1 -> Agent 2", "dim")

    try:
        # Agent 0
        log("Agent 0 - Brand manual genereren uit PDF...", "amber")
        state["huidige_agent"] = 0

        import agent0
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
        product_naam = resultaat.get("product_naam")
        log(f"Agent 0 klaar - {product_naam} (ID: {product_id})", "green")

        time.sleep(3)

        # Agent 1
        log("Agent 1 - Soul ID aanmaken...", "amber")
        state["huidige_agent"] = 1

        try:
            import agent1
            resultaat_1 = agent1.run(product_id=product_id)
            if resultaat_1.get("success"):
                soul_id = resultaat_1.get("soul_id", "")
                log(f"Agent 1 klaar - Soul ID: {soul_id or 'Brand lock opgeslagen'}", "green")
            else:
                log(f"Agent 1 waarschuwing: {resultaat_1.get('bericht')}", "amber")
        except Exception as e:
            log(f"Agent 1 fout: {str(e)}", "red")

        log("Setup volledig klaar!", "green")
        log(f"Product {product_naam} klaar — start dagelijkse pipeline om video's te maken.", "gold")

    except Exception as e:
        log(f"Setup fout: {str(e)}", "red")
    finally:
        state["draait"]        = False
        state["huidige_agent"] = None


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {"status": "AI Pipeline API draait", "versie": "2.0", "draait": state["draait"]}


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


@app.get("/producten")
def get_producten():
    data = supabase_get("producten", "select=*&order=id.desc")
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
    """Upload PDF en start setup: Agent 0 -> Agent 1 -> Agent 2"""
    if state["draait"]:
        return {"success": False, "bericht": "Pipeline draait al - wacht tot die klaar is"}

    if not pdf.filename.lower().endswith(".pdf"):
        return {"success": False, "bericht": "Alleen PDF bestanden zijn toegestaan"}

    pdf_bytes = await pdf.read()

    if len(pdf_bytes) == 0:
        return {"success": False, "bericht": "PDF bestand is leeg"}

    log(f"PDF ontvangen: {pdf.filename} ({len(pdf_bytes)} bytes)", "gold")

    background_tasks.add_task(
        run_setup_taak,
        pdf_bytes, product_naam, product_url, product_foto, doelland, doeltaal
    )

    return {
        "success": True,
        "bericht": f"PDF {pdf.filename} ontvangen - setup gestart (Agent 0 -> 1 -> 2)"
    }


class PipelineStart(BaseModel):
    product_id: Optional[int] = None


@app.post("/pipeline/starten")
def start_pipeline(data: PipelineStart, background_tasks: BackgroundTasks):
    if state["draait"]:
        return {"success": False, "bericht": "Pipeline draait al"}
    background_tasks.add_task(run_pipeline_taak, data.product_id)
    return {"success": True, "bericht": "Pipeline gestart"}


@app.post("/pipeline/stoppen")
def stop_pipeline():
    if state["proces"]:
        state["proces"].terminate()
        log("Pipeline gestopt door gebruiker", "amber")
    state["draait"]        = False
    state["huidige_agent"] = None
    return {"success": True, "bericht": "Pipeline gestopt"}


@app.delete("/logs")
def clear_logs():
    state["logs"] = []
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    print("AI Pipeline API starten op http://localhost:8000")
    print("Dashboard: http://localhost:8000/dashboard")
    uvicorn.run(app, host="0.0.0.0", port=8000)
