# BACK-34: Balance de N y P con datos de manejo cargados por el usuario

- **Issue:** EREIA-6 (Multica)
- **Módulos:** BACK, FRONT, ML
- **Depende de:** —

## Objetivo

Que cada lote lleve un balance estimado de nitrógeno y fósforo a partir de sus cosechas reales y de la fertilización cargada. Así "ya hiciste un cultivo fuerte la campaña pasada" sale de los datos y no de una regla fija. Es el paso más barato hacia el estado del lote de ML-28 y no requiere reentrenar.

## Contexto

- `campaigns` ya guarda cultivo, `fecha_inicio`, `fecha_fin`, `rinde_kg_ha` y `resultado_notas` ([`backend/sql/schema.sql`](../backend/sql/schema.sql)).
- Faltan la fertilización (N y P en kg/ha), la fecha de siembra real separada de la de inicio de campaña, el cultivar o híbrido y el análisis de suelo opcional.
- Ejemplo de magnitud: un maíz de 10 t/ha exporta del orden de 120 kg de N y 30 kg de P.
- Con 2 o 3 cosechas cargadas se puede estimar el desvío propio del lote contra su departamento: un ajuste que se acerca a 0 con pocos datos y personaliza el rinde en kg/ha.

## Alcance por módulo

### BACK

- Archivos: `backend/sql/schema.sql`, `backend/schemas.py`, `backend/routers/campaigns.py`, tests.
- Cambios:
  - Columnas nuevas en `campaigns`: `fert_n_kg_ha`, `fert_p_kg_ha`, `fecha_siembra`, `cultivar`. Tabla o columna `jsonb` para el análisis de suelo del campo (P, K, pH, MO, fecha).
  - Validaciones con rangos razonables.
  - Exponer el balance por campo (en `GET /fields/{id}` o en un endpoint nuevo).

### ML

- Archivos: `backend/services/rotation_matrix.py` o un módulo nuevo `backend/ml/nutrientes.py`, tests.
- Cambios:
  - Exportación por grano (kg de N y de P por tonelada, por cultivo) − fertilización − fijación biológica (soja, vicia). Balance acumulado de las últimas campañas.
  - Sin fertilización cargada, se supone el manejo típico de la zona y se informa.
  - Desvío propio del lote contra el departamento con contracción hacia 0 (por ejemplo, empírico bayesiano).

### FRONT

- Archivos: `frontend/src/components/AccionesCampana.tsx`, `RegistrarSiembraForm.tsx`, `src/types/api.ts`, `src/services/fieldsClient.ts`.
- Cambios: campos opcionales de fertilización, fecha de siembra y cultivar al registrar o cerrar la campaña. Resumen del balance en Info general, en lenguaje de productor ("Su lote exportó ~160 kg de N en las últimas 2 campañas").

## Criterios de aceptación

- [ ] Se pueden cargar la fertilización, la fecha de siembra y el cultivar sin romper las campañas existentes (todo opcional).
- [ ] El balance de N y P de un lote con dos cosechas cargadas coincide con un cálculo a mano en un test.
- [ ] Sin fertilización cargada, la respuesta lo dice explícitamente.
- [ ] Los coeficientes de exportación y fijación tienen su fuente citada en el código.

## Cómo verificar

```bash
cd backend && python -m pytest -q
cd frontend && npm run build && npm run lint
```

## Fuera de alcance

- Usar el balance en el puntaje o en el planificador (ML-28).
- Leer el PDF del laboratorio (posible tarea aparte).

## Preguntas abiertas

- ¿Coeficientes de exportación de qué fuente (IPNI, INTA)?
- ¿El balance se muestra ya en Info general o espera a ML-28?
