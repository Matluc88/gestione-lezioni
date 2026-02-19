"""
Configurazione Gunicorn per Render
"""

# Timeout aumentato per gestire PDF scansionati con visione Claude
timeout = 180  # 3 minuti per PDF complessi

# Numero di workers
workers = 2

# Bind
bind = "0.0.0.0:10000"

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
