"""
Agent 4 — Video Generator
Converteert scripts naar Higgsfield video prompts en genereert 2 video's.

Gebruik:
  python agent4.py --run-id 1
  python agent4.py --product-id 14
"""

import urllib.request
import urllib.error
import json
import time
import os
import argparse
import urllib.parse
import base64
from config import (
    SUPABASE_URL, SUPABASE_KEY,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    HIGGSFIELD_KEY, HIGGSFIELD_API_ID
)

# Higgsfield auth
HIGGSFIELD_AUTH = f"Basic {base64.b64encode(f'{HIGGSFIELD_API_ID}:{HIGGSFIELD_KEY}'.encode()).decode()}"

# ============================================================
# SYSTEM PROMPT
# ============================================================

AGENT_4_PROMPT = """
Je bent een AI video director gespecialiseerd in Higgsfield AI video generatie.
Converteer een video script naar een Higgsfield prompt met vaste brand lock structuur.

HIGGSFIELD MODELLEN:
- UGC / testimonial (persoon in beeld): gebruik "seedance_1_lite"
- Productshot / how-to (geen persoon): gebruik "kling3_0"
  → Als productfoto beschikbaar is wordt dit automatisch image-to-video
  → De prompt beschrijft dan de BEWEGING en CAMERA, niet het product zelf
  → Het product ziet er altijd hetzelfde uit omdat het startframe de echte productfoto is

PROMPT AANPASSING voor image-to-video productshots:
- Beschrijf de camera beweging en sfeer — NIET het product
- Het product staat al vast via de startfoto
- Focus op: lichtval, beweging, compositie, sfeer

PROMPT STRUCTUUR (altijd deze volgorde):
[BRAND OPEN] + [SHOT CONTENT] + [BRAND CLOSE]

BRAND OPEN = sfeer, belichting, kleurpalet, stijl — altijd hetzelfde per merk
SHOT CONTENT = wat er specifiek in deze video gebeurt — wisselt per video
BRAND CLOSE = product zichtbaar, merkkleur accent, premium gevoel — altijd hetzelfde

REGELS:
- Schrijf in het Engels
- Maximaal 450 tekens totaal
- Verwerk soul_id als: "featuring soul character [soul_id]" als soul_id beschikbaar is
- Verwerk merkkleur hex codes expliciet
- Geen tekst, watermerken of logos in beeld

Return ALLEEN pure JSON:
{
  "higgsfield_model": "kling3_0",
  "aspect_ratio": "9:16",
  "duratie": 8,
  "prompt": "[BRAND OPEN] ... [SHOT CONTENT] ... [BRAND CLOSE]",
  "negatieve_prompt": "blurry, low quality, watermark, text overlay, cartoon, distorted, logo",
  "muziek_richting": "",
  "soul_id_gebruikt": true
}
"""

# ============================================================
# HELPERS
# ============================================================

def claude_call(system_prompt, user_message, max_tokens=1000):
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
        print(f"[Supabase] Patch fout: {e.code}")
        return False


# ============================================================
# HIGGSFIELD VIDEO GENERATIE
# ============================================================

def bouw_brand_lock(product):
    """
    Bouwt de vaste brand lock template voor dit product.
    Dit is de basis die bij elke video hetzelfde blijft.
    """
    pk        = product.get("primaire_kleur", "")
    sk        = product.get("secondaire_kleur", "")
    soul_hex  = product.get("soul_hex_kleuren", "")
    vibe      = product.get("vibe_beschrijving", "")
    tempo     = product.get("editing_tempo", "slow cinematic")
    grading   = product.get("editing_kleurgrading", "warm, soft, premium")
    prod_ref  = product.get("product_reference_prompt", "")
    soul_id   = product.get("soul_id", "")

    brand_open = (
        f"Cinematic {tempo} shot. Color palette: {pk}, {sk}. "
        f"{grading} color grading. {vibe} "
    )

    brand_close = (
        f"Product visible: {prod_ref[:100] if prod_ref else 'product in frame'}. "
        f"Premium brand aesthetic. 9:16 vertical. No text, no logo."
    )

    soul_instructie = f"featuring soul character {soul_id}" if soul_id else ""

    return {
        "brand_open":      brand_open,
        "brand_close":     brand_close,
        "soul_id":         soul_id,
        "soul_instructie": soul_instructie
    }


def genereer_higgsfield_prompt(script, product):
    """Converteert een script naar een Higgsfield prompt met brand lock."""

    brand_lock = bouw_brand_lock(product)

    user_message = (
        "Converteer dit video script naar een Higgsfield prompt met brand lock structuur.\n\n"
        f"SCRIPT:\n{json.dumps(script, ensure_ascii=False, indent=2)}\n\n"
        f"BRAND OPEN (gebruik dit altijd aan het begin):\n{brand_lock['brand_open']}\n\n"
        f"BRAND CLOSE (gebruik dit altijd aan het einde):\n{brand_lock['brand_close']}\n\n"
        + (f"SOUL ID (voeg toe als soul character):\n{brand_lock['soul_instructie']}\n\n" if brand_lock['soul_id'] else "")
        + "Bouw de prompt als: [BRAND OPEN] + [SHOT CONTENT uit script] + [BRAND CLOSE]\n"
        "Return ALLEEN pure JSON."
    )

    output = claude_call(AGENT_4_PROMPT, user_message, max_tokens=1000)
    params = parse_json(output)

    if params:
        params["soul_id"]           = brand_lock["soul_id"]
        params["brand_lock_open"]   = brand_lock["brand_open"]
        params["product_image_url"] = product.get("product_image_url", "")

    return params


def genereer_video_higgsfield(prompt_params):
    """
    Genereert een video via Higgsfield SDK.
    Retourneert job_id of video URL.
    """
    if not HIGGSFIELD_KEY or HIGGSFIELD_KEY == "jouw_higgsfield_api_key_hier":
        print("[Agent 4] Higgsfield API key niet ingesteld — prompt opgeslagen")
        return None

    try:
        import os as _os
        _os.environ["HF_API_KEY"]    = HIGGSFIELD_API_ID
        _os.environ["HF_API_SECRET"] = HIGGSFIELD_KEY
        import higgsfield_client

        # Vertaal model namen naar correcte Higgsfield SDK namen
        model_map = {
            "kling3_0":       "kwai/kling/v3-0/text-to-video",
            "seedance_1_lite": "higgsfield-ai/seedance/v1-lite/text-to-video",
            "seedance":        "higgsfield-ai/seedance/v1-lite/text-to-video",
            "kling":           "kwai/kling/v3-0/text-to-video"
        }
        raw_model = prompt_params.get("higgsfield_model", "kling3_0")
        model     = model_map.get(raw_model, raw_model)
        prompt = prompt_params.get("prompt", "")

        print(f"[Agent 4] Genereren via Higgsfield — model: {model}")

        # Bepaal of we image-to-video gebruiken
        product_image_url = prompt_params.get("product_image_url", "")
        is_productshot    = prompt_params.get("higgsfield_model", "") in [
            "kling3_0", "kwai/kling/v3-0/text-to-video",
            "kwai/kling/v3-0/image-to-video"
        ]

        # Gebruik image-to-video voor productshots als productfoto beschikbaar is
        if product_image_url and is_productshot:
            model = "kwai/kling/v3-0/image-to-video"
            print(f"[Agent 4] Image-to-video modus — productfoto als startframe")

        # Bouw Higgsfield argumenten
        hf_args = {
            "prompt":          prompt,
            "negative_prompt": prompt_params.get("negatieve_prompt", ""),
            "aspect_ratio":    prompt_params.get("aspect_ratio", "9:16"),
            "duration":        prompt_params.get("duratie", 8)
        }

        # Voeg productfoto toe als start_image voor image-to-video
        if product_image_url and is_productshot:
            hf_args["start_image"] = product_image_url

        # Voeg Soul ID toe voor UGC/testimonial videos
        soul_id = prompt_params.get("soul_id", "")
        if soul_id and not is_productshot:
            hf_args["soul_id"] = soul_id

        result = higgsfield_client.subscribe(model, arguments=hf_args)

        # Haal video URL op
        videos = result.get("videos", [])
        if videos:
            url = videos[0].get("url", "")
            print(f"[Agent 4] ✓ Video gegenereerd: {url[:60]}...")
            return url

        jobs = result.get("jobs", [])
        if jobs:
            job_id = jobs[0].get("id", "")
            print(f"[Agent 4] Job gestart: {job_id}")
            return job_id

        print(f"[Agent 4] Onverwacht response: {str(result)[:200]}")
        return None

    except ImportError:
        print("[Agent 4] higgsfield-client niet geïnstalleerd")
        print("Voer uit: pip install higgsfield-client")
        return None
    except Exception as e:
        print(f"[Agent 4] Higgsfield fout: {e}")
        return None


# ============================================================
# HOOFDFUNCTIES
# ============================================================

def haal_pipeline_run_op(run_id=None, product_id=None):
    """Haalt de laatste pipeline run op met scripts."""
    if run_id:
        data = supabase_get("pipeline_runs", f"select=*&id=eq.{run_id}")
    elif product_id:
        data = supabase_get("pipeline_runs", f"select=*&product_id=eq.{product_id}&order=aangemaakt_op.desc&limit=1")
    else:
        data = supabase_get("pipeline_runs", "select=*&order=aangemaakt_op.desc&limit=1")

    if not data:
        print("[Agent 4] Geen pipeline run gevonden — eerst Agent 3 uitvoeren")
        return None

    run = data[0]
    print(f"[Agent 4] Pipeline run geladen: ID {run.get('id')} — {run.get('product_naam')}")
    return run


def haal_product_op(product_id):
    """Haalt product op voor visuele context."""
    data = supabase_get("producten", f"select=*&id=eq.{product_id}")
    return data[0] if data else {}


def run(run_id=None, product_id=None):
    """Voert Agent 4 uit."""
    print("\n" + "=" * 60)
    print("  AGENT 4 — VIDEO GENERATOR")
    print("=" * 60)

    # Haal pipeline run op
    pipeline_run = haal_pipeline_run_op(run_id, product_id)
    if not pipeline_run:
        return {"success": False, "bericht": "Geen pipeline run gevonden"}

    run_id_actual = pipeline_run.get("id")
    prod_id       = pipeline_run.get("product_id")
    product_naam  = pipeline_run.get("product_naam", "")

    # Haal scripts op
    scripts = pipeline_run.get("video_script", {}) or {}
    if isinstance(scripts, str):
        try:
            scripts = json.loads(scripts)
        except:
            scripts = {}

    script_1 = scripts.get("script_1", {})
    script_2 = scripts.get("script_2", {})

    if not script_1 or not script_2:
        print("[Agent 4] Geen scripts gevonden — eerst Agent 3 uitvoeren")
        return {"success": False, "bericht": "Geen scripts gevonden"}

    # Haal product op voor visuele context
    product = haal_product_op(prod_id) if prod_id else {}

    # Genereer Higgsfield prompts
    print("\n[Agent 4] Higgsfield prompts genereren...")
    params_1 = genereer_higgsfield_prompt(script_1, product)
    time.sleep(3)
    params_2 = genereer_higgsfield_prompt(script_2, product)

    if not params_1 or not params_2:
        return {"success": False, "bericht": "Prompt generatie mislukt"}

    print(f"\n[Agent 4] Prompt 1: {params_1.get('prompt', '')[:100]}...")
    print(f"[Agent 4] Model 1: {params_1.get('higgsfield_model', '')}")
    print(f"\n[Agent 4] Prompt 2: {params_2.get('prompt', '')[:100]}...")
    print(f"[Agent 4] Model 2: {params_2.get('higgsfield_model', '')}")

    # Genereer video's via Higgsfield
    print("\n[Agent 4] Video's genereren via Higgsfield...")
    video_url_1 = genereer_video_higgsfield(params_1)
    if video_url_1:
        time.sleep(5)
    video_url_2 = genereer_video_higgsfield(params_2)

    # Sla op in Supabase
    update_data = {
        "kling_prompt":  params_1.get("prompt", ""),
        "video_status":  "Gegenereerd" if video_url_1 else "Prompts klaar",
        "video_url":     video_url_1 or "",
    }

    supabase_patch("pipeline_runs", f"id=eq.{run_id_actual}", update_data)

    print("\n" + "=" * 60)
    print("  AGENT 4 KLAAR")
    print(f"  Product: {product_naam}")
    print(f"  Video 1: {video_url_1 or 'Prompt gegenereerd — Higgsfield key nodig'}")
    print(f"  Video 2: {video_url_2 or 'Prompt gegenereerd — Higgsfield key nodig'}")
    print("  Volgende stap: python agent5.py")
    print("=" * 60)

    return {
        "success":      True,
        "run_id":       run_id_actual,
        "video_url_1":  video_url_1,
        "video_url_2":  video_url_2,
        "prompt_1":     params_1,
        "prompt_2":     params_2,
        "bericht":      "Video's gegenereerd"
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 4 — Video Generator")
    parser.add_argument("--run-id",      type=int, help="Pipeline run ID")
    parser.add_argument("--product-id",  type=int, help="Product ID")
    args = parser.parse_args()

    resultaat = run(
        run_id=args.run_id,
        product_id=args.product_id
    )

    print(f"\nResultaat: {json.dumps({k: v for k, v in resultaat.items() if k not in ['prompt_1', 'prompt_2']}, indent=2, ensure_ascii=False)}")

    if resultaat.get("prompt_1"):
        print("\nHIGGSFIELD PROMPT 1:")
        print(json.dumps(resultaat["prompt_1"], indent=2, ensure_ascii=False))
    if resultaat.get("prompt_2"):
        print("\nHIGGSFIELD PROMPT 2:")
        print(json.dumps(resultaat["prompt_2"], indent=2, ensure_ascii=False))
