"""
Configurazione Gunicorn per Render (Standard: 2 GB RAM, 1 CPU)
"""

# Timeout aumentato per gestire PDF scansionati con visione Claude
timeout = 360  # 6 minuti per PDF complessi

# 2 workers su piano Standard (2 GB RAM)
workers = 2

# Ricicla ogni worker dopo N richieste per prevenire memory leak graduali
max_requests = 100
max_requests_jitter = 10

# Bind
bind = "0.0.0.0:10000"

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
