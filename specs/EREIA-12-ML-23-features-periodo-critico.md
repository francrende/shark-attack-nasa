# ML-23: Features nuevas del período crítico

- **Issue:** EREIA-12 (Multica)
- **Módulos:** ML, BACK
- **Depende de:** ML-19, ML-22

## Objetivo

Subir el techo del modelo con clima conocido (R² 0,30) con features agronómicas en lugar de atajos de la hackathon. Sirven para M1 (ML-19) y para M2 (ML-24).

## Contexto

- Hoy:
  - `indice_aridez_evaporativa` usa `EVPTRNS` (evapotranspiración real, no demanda) y casi no aporta.
  - Hay un solo umbral de calor (34 °C).
  - El calendario y el período crítico son fijos para toda la región (`OFFSET_PERIODO_CRITICO` en [`backend/ml/calendario_siembra.py`](../backend/ml/calendario_siembra.py)).
  - No se ve el exceso hídrico (2017/18).
- Las fórmulas viven en [`backend/providers/features.py`](../backend/providers/features.py) y las comparten entrenamiento y producción.

## Alcance por módulo

### ML

- Archivos: `backend/ml/calendario_siembra.py`, `backend/ml/generate_dataset.py`, `backend/ml/train_baseline.py`, `backend/ml/escenarios.py`, dataset y bundle.
- Cambios:
  1. **ET0 FAO-56 Penman-Monteith** y lluvia menos demanda.
  2. **Balance hídrico diario tipo balde:** capacidad de agua útil desde textura y carbono (Saxton–Rawls), consumo `Kc` de FAO-56 × ET0. Salidas: agua útil al inicio del período crítico y días con estrés.
  3. **Fenología por grados-día**, con el período crítico corrido según la latitud y la fecha de siembra real.
  4. **Umbral de calor por cultivo y etapa:** maíz > 35 °C en floración, soja > 32–35 °C en R3–R5, trigo > 30 °C en llenado.
  5. **Exceso hídrico:** días con el perfil casi saturado y meses con lluvia muy alta.
  6. **Napa freática** si hay dato (freatímetros de BCR e INTA; GRACE-FO como dato regional).
- **Dataset y versión:** el de ML-19 (1981–2024), con el clima de ML-22.
- **Métrica objetivo con umbral:** MAE What-If (clima conocido) al menos un 5 % menor que el bundle de ML-19, y el Brier fuera de muestra en producción no empeora. Cada feature nueva se justifica con una ablación.
- **Baseline de comparación:** bundle resultante de ML-19.

### BACK

- Archivos: `backend/providers/features.py`, tests.
- Cambios: las funciones nuevas quedan en `features.py` (paridad entrenamiento/producción). Si el balance hídrico necesita la serie diaria desde la siembra, se lee de la caché por celda.

## Criterios de aceptación

- [ ] Funciones puras con tests unitarios (ET0 contra un caso de FAO-56, balance contra un caso a mano).
- [ ] Ablación por feature en el PR.
- [ ] Se cumple la métrica objetivo; `/simulate` < 1,5 s.

## Cómo verificar

```bash
cd backend && python -m pytest providers/test_features.py ml -q && python -m ml.train_baseline
```

## Fuera de alcance

- Modelo directo de producción (ML-24).
- NDVI (ML-25).
