import { useEffect, useState } from 'react'
import {
  Calendar,
  CloudRain,
  Flame,
  History,
  Pause,
  Play,
  Sprout,
} from 'lucide-react'
import {
  getHistoricalSeriesForCoords,
  HISTORICAL_METRICS,
  HISTORICAL_YEARS,
  type HistoricalMetricId,
  type YearRecord,
} from '../data/historicalData'
import type { Coordenadas } from '../types/api'

interface HistoricalPanelProps {
  ubicacion: Coordenadas
  loteLabel: string
  selectedYear: number
  selectedMetric: HistoricalMetricId
  onChangeYear: (year: number) => void
  onChangeMetric: (metric: HistoricalMetricId) => void
}

function getFamilyBadgeLabel(
  familia: YearRecord['familiaCultivo']
): { text: string; className: string } {
  switch (familia) {
    case 'graminea':
      return {
        text: 'Gramínea · Suma rastrojo',
        className: 'crop-fam-badge graminea',
      }
    case 'leguminosa':
      return {
        text: 'Leguminosa · Poca cobertura',
        className: 'crop-fam-badge leguminosa',
      }
    case 'oleaginosa':
      return {
        text: 'Oleaginosa · Raíz profunda',
        className: 'crop-fam-badge oleaginosa',
      }
    case 'crucifera':
      return {
        text: 'Ciclo corto',
        className: 'crop-fam-badge oleaginosa',
      }
  }
}

export function HistoricalPanel({
  ubicacion,
  loteLabel,
  selectedYear,
  selectedMetric,
  onChangeYear,
  onChangeMetric,
}: HistoricalPanelProps) {
  const [isPlaying, setIsPlaying] = useState<boolean>(false)

  const series = getHistoricalSeriesForCoords(ubicacion)
  const currentRecord =
    series.find((r) => r.year === selectedYear) ?? series[series.length - 1]
  const currentMetricMeta =
    HISTORICAL_METRICS.find((m) => m.id === selectedMetric) ??
    HISTORICAL_METRICS[0]

  // Reproducción automática año por año sincronizada con el mapa
  useEffect(() => {
    if (!isPlaying) return
    const timer = window.setInterval(() => {
      const idx = HISTORICAL_YEARS.indexOf(
        selectedYear as (typeof HISTORICAL_YEARS)[number]
      )
      const nextIdx = (idx + 1) % HISTORICAL_YEARS.length
      onChangeYear(HISTORICAL_YEARS[nextIdx])
    }, 1400)

    return () => window.clearInterval(timer)
  }, [isPlaying, selectedYear, onChangeYear])

  // Valor numérico y porcentaje de barra para las variables cuantitativas
  function getMetricBarAndLabel(rec: YearRecord): {
    valueLabel: string
    subLabel: string
    percent: number
    fillClass: string
  } {
    switch (selectedMetric) {
      case 'lluvias':
        return {
          valueLabel: `${rec.lluviaAnualMm} mm`,
          subLabel: `${rec.aguaRaicesPct}% agua en raíces · Campaña ${rec.estadoCampana.toLowerCase()}`,
          percent: Math.min(100, Math.round((rec.lluviaAnualMm / 1150) * 100)),
          fillClass: 'water-fill',
        }
      case 'evaporacion':
        return {
          valueLabel: `${rec.evaporacionMmDia} mm/día`,
          subLabel:
            rec.evaporacionMmDia >= 5.2
              ? 'Demanda muy alta de agua por calor y sol'
              : 'Demanda moderada del ambiente',
          percent: Math.min(
            100,
            Math.round((rec.evaporacionMmDia / 6.5) * 100)
          ),
          fillClass: 'water-fill-light',
        }
      case 'temperatura':
        return {
          valueLabel: `${rec.diasGolpeCalor} días > 34 °C`,
          subLabel: `Máxima promedio en verano: ${rec.tempMaxVeranoC} °C`,
          percent: Math.min(100, Math.round((rec.diasGolpeCalor / 24) * 100)),
          fillClass: 'heat-fill',
        }
      case 'suelo':
        return {
          valueLabel: `${rec.materiaOrganicaGKg} g/kg`,
          subLabel: `Sembrado: ${rec.cultivoVeranoNombre}`,
          percent: Math.min(
            100,
            Math.round(((rec.materiaOrganicaGKg - 12) / 14) * 100)
          ),
          fillClass: 'soil-fill',
        }
      case 'cultivos':
      default:
        return {
          valueLabel: rec.cultivoVeranoNombre,
          subLabel: `Invierno: ${rec.cultivoInvierno}`,
          percent: 100,
          fillClass: 'winner-bar',
        }
    }
  }

  return (
    <>
      {/* TARJETA 1: CONTROL DE AÑO (2017–2026) Y SELECTOR DESPLEGABLE DE DATO HISTÓRICO */}
      <section className="panel-section historical-controls-section">
        <div className="section-header-row">
          <div>
            <span className="section-eyebrow">
              <History size={13} />
              <span>SERIE HISTÓRICA DE 10 AÑOS (2017–2026)</span>
            </span>
            <h2 className="section-title">Información histórica</h2>
            <p className="telemetry-lote-subtitle">{loteLabel}</p>
          </div>
          <span className="historical-year-hero-badge">{selectedYear}</span>
        </div>

        {/* CONTROL DESLIZANTE DE AÑO EN TIEMPO REAL CON EL MAPA */}
        <div className="year-timeline-box">
          <div className="year-timeline-header">
            <div className="year-timeline-label">
              <Calendar size={14} />
              <span>
                Seleccione el año para visualizar en el mapa:{' '}
                <strong>Campaña {selectedYear}</strong>
              </span>
            </div>
            <button
              type="button"
              className="play-timeline-btn"
              onClick={() => setIsPlaying((prev) => !prev)}
            >
              {isPlaying ? <Pause size={14} /> : <Play size={14} />}
              <span>{isPlaying ? 'Pausar' : 'Reproducir serie'}</span>
            </button>
          </div>

          <input
            type="range"
            className="ag-range year-range"
            aria-label="Seleccionar año histórico entre 2017 y 2026"
            min={2017}
            max={2026}
            step={1}
            value={selectedYear}
            onChange={(e) => {
              setIsPlaying(false)
              onChangeYear(Number(e.target.value))
            }}
          />

          <div className="year-pills-row">
            {HISTORICAL_YEARS.map((yr) => (
              <button
                key={yr}
                type="button"
                className={`year-step-pill ${yr === selectedYear ? 'active' : ''}`}
                onClick={() => {
                  setIsPlaying(false)
                  onChangeYear(yr)
                }}
              >
                {yr}
              </button>
            ))}
          </div>
        </div>

        {/* MENÚ DESPLEGABLE PARA ELEGIR EL DATO HISTÓRICO */}
        <div className="control-group">
          <label className="control-label" htmlFor="historical-metric-select">
            <span>Variable histórica a visualizar</span>
          </label>
          <select
            id="historical-metric-select"
            className="ag-select"
            value={selectedMetric}
            onChange={(e) =>
              onChangeMetric(e.target.value as HistoricalMetricId)
            }
          >
            {HISTORICAL_METRICS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
          <p className="what-if-helper-text">{currentMetricMeta.helperText}</p>
        </div>
      </section>

      {/* TARJETA 2: RESUMEN DE LA CAMPAÑA SELECCIONADA + EVOLUCIÓN EN LOS 10 AÑOS */}
      <section className="panel-section historical-series-section">
        {/* Resumen rápido del año elegido (máx 3 métricas clave) */}
        <div className="selected-year-summary-card">
          <div className="selected-year-summary-top">
            <div>
              <span className="winner-kicker">Campaña {selectedYear}</span>
              <h3 className="selected-year-crop-title">
                {currentRecord.cultivoVeranoNombre}
              </h3>
              <p className="winner-crop-subtitle">
                Invierno previo: <strong>{currentRecord.cultivoInvierno}</strong>{' '}
                · Clima: <strong>{currentRecord.estadoCampana}</strong>
              </p>
            </div>
          </div>

          <div className="selected-year-kpis">
            <div className="year-kpi-item water">
              <CloudRain size={15} />
              <div>
                <span className="year-kpi-label">Lluvias y agua</span>
                <strong className="year-kpi-val water">
                  {currentRecord.lluviaAnualMm} mm · {currentRecord.aguaRaicesPct}% en raíces
                </strong>
              </div>
            </div>

            <div className="year-kpi-item heat">
              <Flame size={15} />
              <div>
                <span className="year-kpi-label">Calor y evaporación</span>
                <strong className="year-kpi-val heat">
                  {currentRecord.diasGolpeCalor} días de calor · {currentRecord.evaporacionMmDia} mm/día
                </strong>
              </div>
            </div>

            <div className="year-kpi-item soil">
              <Sprout size={15} />
              <div>
                <span className="year-kpi-label">Materia orgánica</span>
                <strong className="year-kpi-val heat">
                  {currentRecord.materiaOrganicaGKg} g/kg
                </strong>
              </div>
            </div>
          </div>
        </div>

        {/* Serie de 10 años según la opción elegida en el desplegable */}
        <div className="historical-timeline-list">
          {series.map((rec) => {
            const isSelected = rec.year === selectedYear

            if (selectedMetric === 'cultivos') {
              const famBadge = getFamilyBadgeLabel(rec.familiaCultivo)
              return (
                <button
                  key={rec.year}
                  type="button"
                  className={`historical-row-btn ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    setIsPlaying(false)
                    onChangeYear(rec.year)
                  }}
                >
                  <div className="hist-row-left">
                    <span className="hist-year-tag">{rec.year}</span>
                    <div className="hist-crop-stack">
                      <strong className="hist-crop-main">
                        {rec.cultivoVeranoNombre}
                      </strong>
                      <span className="hist-crop-winter">
                        Invierno: {rec.cultivoInvierno} · Campaña{' '}
                        {rec.estadoCampana.toLowerCase()}
                      </span>
                    </div>
                  </div>
                  <span className={famBadge.className}>{famBadge.text}</span>
                </button>
              )
            }

            const barInfo = getMetricBarAndLabel(rec)
            return (
              <button
                key={rec.year}
                type="button"
                className={`historical-row-btn metric-mode ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  setIsPlaying(false)
                  onChangeYear(rec.year)
                }}
              >
                <div className="hist-metric-top">
                  <div className="hist-row-left">
                    <span className="hist-year-tag">{rec.year}</span>
                    <span className="hist-metric-sub">{barInfo.subLabel}</span>
                  </div>
                  <strong className="hist-metric-val">
                    {barInfo.valueLabel}
                  </strong>
                </div>
                <div className="progress-track hist-bar-track">
                  <div
                    className={`progress-fill ${barInfo.fillClass}`}
                    style={{ width: `${Math.max(8, barInfo.percent)}%` }}
                  />
                </div>
              </button>
            )
          })}
        </div>
      </section>
    </>
  )
}
