import {
  Calendar,
  Play,
  RotateCcw,
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

interface CampaignConfigProps {
  campana: Campana | null
  cultivoAnterior: CultivoId | null
  objetivoProductor: ObjetivoProductor
  canPlan: boolean
  isPlanning: boolean
  isHistoricalReady: boolean
  onChangeCampana: (campana: Campana) => void
  onChangeCultivoAnterior: (cultivo: CultivoId) => void
  onChangeObjetivo: (objetivo: ObjetivoProductor) => void
  onPlan: () => void
}

interface WhatIfPanelProps {
  whatIf: SimulacionWhatIf
  nasaDetectedHumidityPct: number
  onChangeWhatIf: (whatIf: SimulacionWhatIf) => void
  onResetWhatIf: () => void
}

const TODOS_LOS_CULTIVOS = Object.values(CULTIVOS_CATALOGO)
const OBJETIVOS_KEYS: ObjetivoProductor[] = [
  'resiliencia_hidroclimatica',
  'equilibrio',
  'conservacion_suelo',
]

/**
 * TARJETA 1 PRINCIPAL EN PLANIFICACIÓN DE CAMPAÑA:
 * Selección de Tipo de campaña, Cultivo antecesor y Prioridad de manejo
 */
export function CampaignConfigPanel({
  campana,
  cultivoAnterior,
  objetivoProductor,
  canPlan,
  isPlanning,
  isHistoricalReady,
  onChangeCampana,
  onChangeCultivoAnterior,
  onChangeObjetivo,
  onPlan,
}: CampaignConfigProps) {
  return (
    <section className="panel-section controls-section">
      <div className="section-header-row">
        <div>
          <h2 className="section-title">Planificación de campaña</h2>
        </div>
      </div>

      <div className="controls-row-2col">
        {/* 1. Tipo de Campaña */}
        <div className="control-group">
          <label className="control-label">
            <Calendar size={14} />
            <span>Campaña a planificar</span>
          </label>
          <div
            className="campaign-toggle"
            role="group"
            aria-label="Seleccionar campaña a planificar"
          >
            <button
              type="button"
              className={`campaign-btn summer-btn ${campana === 'verano' ? 'active' : ''}`}
              onClick={() => onChangeCampana('verano')}
            >
              <Sun size={15} />
              <span>Campaña gruesa (verano)</span>
            </button>
            <button
              type="button"
              className={`campaign-btn winter-btn ${campana === 'invierno' ? 'active' : ''}`}
              onClick={() => onChangeCampana('invierno')}
            >
              <Snowflake size={15} />
              <span>Campaña fina (invierno)</span>
            </button>
          </div>
        </div>

        {/* 2. Cultivo Antecesor */}
        <div className="control-group">
          <label className="control-label" htmlFor="cultivo-anterior-select">
            <span>Cultivo antecesor en el lote</span>
          </label>
          <select
            id="cultivo-anterior-select"
            className="ag-select"
            value={cultivoAnterior ?? ''}
            onChange={(e) => {
              if (e.target.value) {
                onChangeCultivoAnterior(e.target.value as CultivoId)
              }
            }}
          >
            <option value="" disabled>
              Seleccione el cultivo antecesor...
            </option>
            <optgroup label="Campaña gruesa (verano)">
              {TODOS_LOS_CULTIVOS.filter((c) => c.campana === 'verano').map(
                (c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                )
              )}
            </optgroup>
            <optgroup label="Campaña fina (invierno y coberturas)">
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

      {/* 3. Prioridad de manejo */}
      <div className="control-group">
        <label className="control-label">
          <Sparkles size={14} />
          <span>Prioridad de manejo</span>
        </label>
        <div
          className="objective-cards-grid"
          role="radiogroup"
          aria-label="Prioridad de la campaña"
        >
          {OBJETIVOS_KEYS.map((key) => {
            const meta = OBJETIVOS_PRODUCTOR_META[key]
            const isSelected = objetivoProductor === key
            return (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={isSelected}
                className={`objective-card obj-${key} ${isSelected ? 'selected' : ''}`}
                onClick={() => onChangeObjetivo(key)}
              >
                <span className="objective-title">{meta.titulo}</span>
                <p className="objective-desc">{meta.subtitulo}</p>
                <div
                  className="objective-mini-split"
                  title="Proporción entre Agua/Clima (azul) y Suelo (naranja)"
                >
                  <span
                    className="mini-split-water"
                    style={{ width: `${meta.pesoClima * 100}%` }}
                  />
                  <span
                    className="mini-split-soil"
                    style={{ width: `${meta.pesoSuelo * 100}%` }}
                  />
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* 4. Acción principal: Planificar */}
      <div className="plan-action-footer">
        <span className="plan-status-hint">
          {!canPlan
            ? 'Seleccione campaña y cultivo antecesor para consultar los datos históricos.'
            : isHistoricalReady
              ? 'Datos históricos cargados. Presione Planificar para ver la recomendación.'
              : 'Cargando datos históricos del lote...'}
        </span>
        <button
          type="button"
          className="plan-submit-btn"
          disabled={!canPlan || isPlanning}
          onClick={onPlan}
        >
          <Play size={14} />
          <span>{isPlanning ? 'Planificando...' : 'Planificar'}</span>
        </button>
      </div>
    </section>
  )
}

/**
 * TARJETA 3 INDEPENDIENTE Y SECUNDARIA EN PLANIFICACIÓN DE CAMPAÑA:
 * Simulador Interactivo de Escenarios Climáticos
 */
export function WhatIfPanel({
  whatIf,
  nasaDetectedHumidityPct,
  onChangeWhatIf,
  onResetWhatIf,
}: WhatIfPanelProps) {
  const isWhatIfModified =
    whatIf.override_humedad_radicular_pct !== null ||
    whatIf.variacion_lluvia_esperada_pct !== 0

  const effectiveHumidity = Math.round(
    whatIf.override_humedad_radicular_pct ?? nasaDetectedHumidityPct
  )
  const rainVariation = Math.round(whatIf.variacion_lluvia_esperada_pct)

  return (
    <section className="panel-section what-if-standalone-section">
      <div className="section-header-row">
        <div>

          <div className="what-if-title-line">
            <h2 className="section-title">Simulación de escenarios</h2>
            {isWhatIfModified && (
              <span className="what-if-active-pill">Escenario simulado</span>
            )}
          </div>
        </div>
        {isWhatIfModified && (
          <button
            type="button"
            className="reset-whatif-btn"
            onClick={onResetWhatIf}
          >
            <RotateCcw size={13} />
            <span>Restablecer datos satelitales</span>
          </button>
        )}
      </div>

      <p className="what-if-helper-text">
        Evalúe escenarios más secos o más húmedos para analizar la respuesta del cultivo recomendado.
      </p>

      <div className="what-if-box">
        <div className="what-if-sliders">
          {/* Slider 1: Agua en las raíces */}
          <div className="slider-control">
            <div className="slider-label-row">
              <span>Agua en las raíces al sembrar</span>
              <strong className="slider-val water">
                {effectiveHumidity}% ·{' '}
                {whatIf.override_humedad_radicular_pct === null
                  ? 'Dato real'
                  : 'Simulado'}
              </strong>
            </div>
            <input
              type="range"
              className="ag-range water-range"
              aria-label="Agua en las raíces al sembrar"
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
              <span>Poca agua (10%)</span>
              <span>Media (50%)</span>
              <span>Mucha agua (95%)</span>
            </div>
          </div>

          {/* Slider 2: Lluvias esperadas */}
          <div className="slider-control">
            <div className="slider-label-row">
              <span>Lluvias esperadas en la campaña</span>
              <strong
                className={`slider-val ${rainVariation < 0 ? 'heat' : 'water'}`}
              >
                {rainVariation > 0 ? `+${rainVariation}%` : `${rainVariation}%`}{' '}
                · {rainVariation === 0 ? 'Normal' : 'Simulado'}
              </strong>
            </div>
            <input
              type="range"
              className="ag-range rain-range"
              aria-label="Lluvias esperadas en la campaña"
              min={-50}
              max={50}
              step={5}
              value={rainVariation}
              onChange={(e) =>
                onChangeWhatIf({
                  ...whatIf,
                  variacion_lluvia_esperada_pct: Number(e.target.value),
                })
              }
            />
            <div className="slider-ticks">
              <span>Más seco (−50%)</span>
              <span>Normal (0%)</span>
              <span>Más lluvioso (+50%)</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
