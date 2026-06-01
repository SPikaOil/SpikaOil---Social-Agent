"""
config.py — Centrale configuratie voor alle agents
Pas dit bestand aan als je credentials wijzigen.
Op de server worden deze overschreven door environment variables.
"""

import os

# ============================================================
# SUPABASE
# ============================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://txuzmuhbmvzqotjuffhv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR4dXptdWhibXZ6cW90anVmZmh2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcwNDMzMTMsImV4cCI6MjA5MjYxOTMxM30.irLNWt6YIN39bOqCiEosBiXJU5jsycG91d0OX3tRVgg")

# ============================================================
# ANTHROPIC (Claude API)
# ============================================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")
ANTHROPIC_MODEL   = "claude-sonnet-4-5"

# ============================================================
# HIGGSFIELD
# ============================================================
HIGGSFIELD_KEY    = os.environ.get("HIGGSFIELD_KEY",    "ed9412d969feb6cbe6fedfe22d975b76e6ace49b0db99286e4b8cf9bbbc21bf9")
HIGGSFIELD_API_ID = os.environ.get("HIGGSFIELD_API_ID", "de6f0431-ba49-490d-b2de-40d5bef228f4")

# ============================================================
# MAKE WEBHOOK (tijdelijk voor publishing)
# ============================================================
MAKE_WEBHOOK = os.environ.get("MAKE_WEBHOOK", "https://hook.eu1.make.com/s6ylud7htx2r2hf1l3j3szuc5nt6mkam")
