# ML-29: Escala de lote

- **Issue:** EREIA-18 (Multica)
- **Módulos:** ML, BACK, FRONT
- **Depende de:** BACK-34 (rindes y manejo del usuario), BACK-35, ML-25

## Objetivo

Bajar de la escala departamental (rinde por departamento, clima a ~50 km, suelo a 250 m) a la del lote, y personalizar la recomendación con los datos propios del productor.

## Contexto

- Hoy el rinde es el del departamento más cercano (`ml/departamentos.py`, hasta 75 km), el suelo sale de SoilGrids (250 m) y la humedad de GWETROOT regional.
- Los rindes que carga el usuario (`campaigns.rinde_kg_ha`) son, además, el dataset propietario de la etapa comercial.

## Alcance por módulo

### ML

- Archivos: módulos nuevos en `backend/ml/`.
- Cambios:
  1. **Calibración por lote:** desvío propio contra el departamento con 2 o 3 cosechas, con contracción hacia 0 si hay pocos datos.
  2. **Ambientes o zonas de manejo (no supervisado):** clustering dentro del lote con suelo, relieve, historia de NDVI y humedad ("loma, media loma, bajo"), con una recomendación por ambiente.
  3. **Transferencia entre lotes parecidos:** un lote sin historia hereda lo aprendido de su grupo.
  4. **Anomalías en el seguimiento:** la curva de NDVI se aparta de campañas parecidas y dispara una alerta.
  5. Opcional: preentrenamiento autosupervisado sobre series de imágenes sin etiqueta y ajuste con los pocos rindes de lote.
- **Dataset y versión:** rindes de lote (usuarios, mapas de cosecha de contratistas, aseguradoras), Sentinel-2/HLS, cartas GeoINTA, SAOCOM.
- **Métrica objetivo con umbral:** en lotes con al menos 3 cosechas, el error en kg/ha validado dejando una campaña afuera es al menos un 10 % menor que el rinde departamental.
- **Baseline de comparación:** rinde departamental de ML-17.

### BACK

- Archivos: `backend/providers/` (cartas de suelo GeoINTA 1:50.000 con Índice de Productividad, humedad SAOCOM de CONAE, recortes Sentinel-2/HLS), `backend/sql/schema.sql`.
- Cambios: suelo y humedad a escala de lote, precalculados por campo en segundo plano. Importación de mapas de cosecha (Shapefile o KML).

### FRONT

- Archivos: `frontend/src/components/MapView.tsx`, componentes nuevos.
- Cambios: ambientes dentro del lote en el mapa e importación de polígonos y mapas de cosecha.

## Criterios de aceptación

- [ ] Se cumple la métrica objetivo en los lotes con datos.
- [ ] Sin datos propios, el comportamiento es el actual (departamental) y la UI lo dice.

## Cómo verificar

```bash
cd backend && python -m pytest -q
cd frontend && npm run build && npm run lint
```

## Fuera de alcance

- Planificador de secuencias (ML-28).

## Preguntas abiertas

- ¿Acceso a SAOCOM (CONAE) y a mapas de cosecha? ¿Qué acuerdo de datos con los usuarios?
