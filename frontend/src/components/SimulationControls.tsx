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

interface CampaignConfigProps {
  campana: Campana
  cultivoAnterior: CultivoId
  objetivoProductor: ObjetivoProductor
  onChangeCampana: (campana: Campana) => void
  onChangeCultivoAnterior: (cultivo: CultivoId) => void
  onChangeObjetivo: (objetivo: ObjetivoProductor) => void
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
 * Selección de Tipo de Campaña, Último Cultivo y Objetivo del Productor.
 */
export function CampaignConfigPanel({
  campana,
  cultivoAnterior,
  objetivoProductor,
  onChangeCampana,
  onChangeCultivoAnterior,
  onChangeObjetivo,
}: CampaignConfigProps) {
  return (
    <section className="panel-section controls-section">
      <div className="section-header-row">
        <div>
          <span className="section-eyebrow">
            <Compass size={13} />
            <span>CONFIGURACIÓN PRINCIPAL DE CAMPAÑA</span>
          </span>
          <h2 className="section-title">Definición de Siembra y Objetivo</h2>
        </div>
      </div>

      <div className="controls-row-2col">
        {/* 1. Tipo de Campaña (Invierno vs Verano) */}
        <div className="control-group">
          <label className="control-label">
            <Calendar size={14} />
            <span>Tipo de Campaña</span>
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

        {/* 2. Último Cultivo */}
        <div className="control-group">
          <label className="control-label" htmlFor="cultivo-anterior-select">
            <span>Último Cultivo (De qué viene el lote)</span>
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

      {/* 3. Objetivo del Productor */}
      <div className="control-group">
        <label className="control-label">
          <Sparkles size={14} />
          <span>Objetivo Principal para esta Campaña</span>
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
                    title={`Peso Agua y Clima: ${Math.round(meta.pesoClima * 100)}%`}
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
    </section>
  )
}

/**
 * TARJETA 3 INDEPENDIENTE EN PLANIFICACIÓN DE CAMPAÑA:
 * Simulador Interactivo "What-If" separado de la configuración principal.
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

  const effectiveHumidity =
    whatIf.override_humedad_radicular_pct ?? nasaDetectedHumidityPct

  return (
    <section className="panel-section what-if-standalone-section">
      <div className="section-header-row">
        <div>
          <span className="section-eyebrow">
            <Sliders size={13} />
            <span>SIMULACIÓN DE ESCENARIOS ("WHAT-IF")</span>
          </span>
          <h2 className="section-title">¿Qué pasa si cambia el clima?</h2>
        </div>
        {isWhatIfModified && (
          <button
            type="button"
            className="reset-whatif-btn"
            onClick={onResetWhatIf}
          >
            <RotateCcw size={13} />
            <span>Volver al dato real</span>
          </button>
        )}
      </div>

      <p className="what-if-helper-text">
        Mové los controles para probar cómo cambiaría el ranking si llueve más o menos antes de sembrar:
      </p>

      <div className="what-if-box">
        <div className="what-if-sliders">
          {/* Slider 1: Override Humedad Radicular */}
          <div className="slider-control">
            <div className="slider-label-row">
              <span>Agua acumulada en las raíces al sembrar</span>
              <strong className="slider-val water">
                {effectiveHumidity}%{' '}
                {whatIf.override_humedad_radicular_pct === null
                  ? '(Dato Real)'
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
              <span>10% (Sequía)</span>
              <span>50% (Media)</span>
              <span>95% (Suelo lleno)</span>
            </div>
          </div>

          {/* Slider 2: Variación de Lluvia Esperada */}
          <div className="slider-control">
            <div className="slider-label-row">
              <span>Variación de lluvias en la campaña</span>
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
              <span>-50% (Más seco)</span>
              <span>0% (Normal)</span>
              <span>+50% (Más lluvioso)</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
