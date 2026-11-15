"""Configuración global de pytest para el backend.

BACK-18: los tests nunca usan la caché persistente de Supabase, aunque el `.env` local tenga
SUPABASE_SECRET_KEY. Sin esto, los tests que levantan la app (`TestClient(app)` corre el
`lifespan`) leerían y escribirían en la tabla real `provider_cache`.
"""

import os

os.environ["CACHE_PERSISTENTE"] = "false"
