import {
  Calendar,
  Compass,
  RotateCcw,
  Sliders,
  Sparkles,
  Sun,
  Snowflake,
} from 'lucide-react'
import {
  CULTIVOS_CATALOGO,
  OBJETIVOS_PRODUCTOR_META,
} from '../data/demoFields'
import type {
  Campana,
  CultivoId,
  ObjetivoProductor,
  SimulacionWhatIf,
} from '../types/api'

interface SimulationControlsProps {
  campana: Campana
  cultivoAnterior: CultivoId
  objetivoProductor: ObjetivoProductor
  whatIf: SimulacionWhatIf
  nasaDetectedHumidityPct: number
  onChangeCampana: (campana: Campana) => void
  onChangeCultivoAnterior: (cultivo: CultivoId) => void
  onChangeObjetivo: (objetivo: ObjetivoProductor) => void
  onChangeWhatIf: (whatIf: SimulacionWhatIf) => void
  onResetWhatIf: () => void
}

const TODOS_LOS_CULTIVOS = Object.values(CULTIVOS_CATALOGO)
const OBJETIVOS_KEYS: ObjetivoProductor[] = [
  'resiliencia_hidroclimatica',
  'equilibrio',
  'conservacion_suelo',
]

export function SimulationControls({
  campana,
  cultivoAnterior,
  objetivoProductor,
  whatIf,
  nasaDetectedHumidityPct,
  onChangeCampana,
  onChangeCultivoAnterior,
  onChangeObjetivo,
  onChangeWhatIf,
  onResetWhatIf,
}: SimulationControlsProps) {
  const isWhatIfModified =
    whatIf.override_humedad_radicular_pct !== null ||
    whatIf.variacion_lluvia_esperada_pct !== 0

  const effectiveHumidity =
    whatIf.override_humedad_radicular_pct ?? nasaDetectedHumidityPct

  return (
    <section className="panel-section controls-section">
      {/* PASO 2: CONFIGURACIÓN DE CAMPAÑA, ANTECESOR Y PRIORIDAD */}
      <div className="section-header-row">
        <div>
          <span className="section-eyebrow">
            <Compass size={13} />
            <span>PASO 2 · ESTRATEGIA Y CONTEXTO DEL LOTE</span>
          </span>
          <h2 className="section-title">Planificación de Campaña</h2>
        </div>
      </div>

      <div className="controls-row-2col">
        {/* Selector de Campaña (Invierno vs Verano) */}
        <div className="control-group">
          <label className="control-label">
            <Calendar size={14} />
            <span>Campaña a Sembrar</span>
          </label>
          <div className="campaign-toggle">
            <button
              type="button"
              className={`campaign-btn ${campana === 'verano' ? 'active' : ''}`}
              onClick={() => onChangeCampana('verano')}
            >
              <Sun size={15} />
              <span>Gruesa (Verano)</span>
            </button>
            <button
              type="button"
              className={`campaign-btn ${campana === 'invierno' ? 'active' : ''}`}
              onClick={() => onChangeCampana('invierno')}
            >
              <Snowflake size={15} />
              <span>Fina (Invierno)</span>
            </button>
          </div>
        </div>

        {/* Selector de Cultivo Anterior */}
        <div className="control-group">
          <label className="control-label" htmlFor="cultivo-anterior-select">
            <span>Cultivo Antecesor (De qué viene el lote)</span>
          </label>
          <select
            id="cultivo-anterior-select"
            className="ag-select"
            value={cultivoAnterior}
            onChange={(e) =>
              onChangeCultivoAnterior(e.target.value as CultivoId)
            }
          >
            <optgroup label="Cultivos de Verano (Gruesa)">
              {TODOS_LOS_CULTIVOS.filter((c) => c.campana === 'verano').map(
                (c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                )
              )}
            </optgroup>
            <optgroup label="Cultivos de Invierno / Coberturas (Fina)">
              {TODOS_LOS_CULTIVOS.filter((c) => c.campana === 'invierno').map(
                (c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                )
              )}
            </optgroup>
          </select>
        </div>
      </div>

      {/* Selector de Objetivo del Productor (Pesos MCDA) */}
      <div className="control-group">
        <label className="control-label">
          <Sparkles size={14} />
          <span>Prioridad Agronómica del Productor (Ponderación MCDA)</span>
        </label>
        <div className="objective-cards-grid">
          {OBJETIVOS_KEYS.map((key) => {
            const meta = OBJETIVOS_PRODUCTOR_META[key]
            const isSelected = objetivoProductor === key
            return (
              <button
                key={key}
                type="button"
                className={`objective-card ${isSelected ? 'selected' : ''}`}
                onClick={() => onChangeObjetivo(key)}
              >
                <div className="objective-card-top">
                  <span className="objective-title">{meta.titulo}</span>
                </div>
                <div className="objective-weights-bar">
                  <span
                    className="weight-segment water"
                    style={{ width: `${meta.pesoClima * 100}%` }}
                    title={`Peso Hidroclimático: ${Math.round(meta.pesoClima * 100)}%`}
                  >
                    {Math.round(meta.pesoClima * 100)}% Agua/Clima
                  </span>
                  <span
                    className="weight-segment soil"
                    style={{ width: `${meta.pesoSuelo * 100}%` }}
                    title={`Peso Salud de Suelo: ${Math.round(meta.pesoSuelo * 100)}%`}
                  >
                    {Math.round(meta.pesoSuelo * 100)}% Suelo
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* PASO 4: SIMULADOR INTERACTIVO "WHAT-IF" */}
      <div className="what-if-box">
        <div className="what-if-header">
          <div className="what-if-title">
            <Sliders size={15} />
            <span>Simulación Interactiva "What-If" (En Tiempo Real)</span>
          </div>
          {isWhatIfModified && (
            <button
              type="button"
              className="reset-whatif-btn"
              onClick={onResetWhatIf}
            >
              <RotateCcw size={13} />
              <span>Restaurar datos NASA</span>
            </button>
          )}
        </div>

        <div className="what-if-sliders">
          {/* Slider 1: Override Humedad Radicular */}
          <div className="slider-control">
            <div className="slider-label-row">
              <span>
                Humedad Radicular Simulada (<code>GWETROOT</code>)
              </span>
              <strong className="slider-val water">
                {effectiveHumidity}%{' '}
                {whatIf.override_humedad_radicular_pct === null
                  ? '(Satélite NASA)'
                  : '(Simulado)'}
              </strong>
            </div>
            <input
              type="range"
              className="ag-range water-range"
              min={10}
              max={95}
              step={1}
              value={effectiveHumidity}
              onChange={(e) =>
                onChangeWhatIf({
                  ...whatIf,
                  override_humedad_radicular_pct: Number(e.target.value),
                })
              }
            />
            <div className="slider-ticks">
              <span>10% (Sequía severa)</span>
              <span>50% (Media)</span>
              <span>95% (Capacidad de campo)</span>
            </div>
          </div>

          {/* Slider 2: Variación de Lluvia Esperada */}
          <div className="slider-control">
            <div className="slider-label-row">
              <span>Variación de Lluvias en Campaña</span>
              <strong
                className={`slider-val ${whatIf.variacion_lluvia_esperada_pct < 0 ? 'heat' : 'water'}`}
              >
                {whatIf.variacion_lluvia_esperada_pct > 0
                  ? `+${whatIf.variacion_lluvia_esperada_pct}%`
                  : `${whatIf.variacion_lluvia_esperada_pct}%`}
              </strong>
            </div>
            <input
              type="range"
              className="ag-range rain-range"
              min={-50}
              max={50}
              step={5}
              value={whatIf.variacion_lluvia_esperada_pct}
              onChange={(e) =>
                onChangeWhatIf({
                  ...whatIf,
                  variacion_lluvia_esperada_pct: Number(e.target.value),
                })
              }
            />
            <div className="slider-ticks">
              <span>-50% (Año Niña Seco)</span>
              <span>0% (Normal)</span>
              <span>+50% (Año Niño Húmedo)</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
