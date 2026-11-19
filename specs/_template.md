# <PREFIJO-N>: <título>

- **Issue:** EREIA-<n> (Multica)
- **Módulos:** BACK | FRONT | ML
- **Depende de:** <issues o "—">

> La spec dice qué hay que lograr y cómo verificarlo. No lleva estado: el estado vive en el issue.

## Objetivo

<Qué problema resuelve y para quién, en 2-4 líneas.>

## Contexto

<Qué existe hoy (archivos, endpoints, datos), por qué hace falta el cambio y qué decisiones ya están tomadas. Enlazá código con rutas relativas.>

## Alcance por módulo

<Borrá los módulos que no apliquen. Si toca más de uno, cada sección tiene que poder implementarse y revisarse por separado.>

### BACK

- Archivos: <rutas>
- Cambios: <endpoints, schemas, servicios, SQL>

### FRONT

- Archivos: <rutas>
- Cambios: <componentes, estados, textos>

### ML

- Archivos: <rutas>
- Cambios: <features, modelo, reglas>
- **Dataset y versión:** <archivo(s), rango de campañas, versión del bundle o commit del dataset de partida>
- **Métrica objetivo con umbral:** <métrica, régimen (producción fuera de muestra / What-If) y valor mínimo; por ejemplo "Brier fuera de muestra contra la frecuencia típica > +3,5 %">
- **Baseline de comparación:** <bundle actual (`training_metrics.json` en <commit>), "año normal", frecuencia típica, etc.>

## Criterios de aceptación

- [ ] <Criterio verificable 1>
- [ ] <Criterio verificable 2>

## Cómo verificar

```bash
<comandos exactos: tests, entrenamiento, requests de ejemplo>
```

<Pasos manuales si hacen falta (por ejemplo, en Render o en el navegador).>

## Fuera de alcance

- <Qué no se hace en esta tarea y adónde va>

## Preguntas abiertas

- <Decisiones que hay que cerrar con el equipo antes de implementar; borrá la sección si no hay>
