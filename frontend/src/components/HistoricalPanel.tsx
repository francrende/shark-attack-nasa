import { useEffect, useState } from 'react'
import { Calendar, CloudRain, Droplets, Info, Pause, Play, Sprout } from 'lucide-react'
import {
  HISTORICAL_METRICS,
  TEXTO_NIVEL_LLUVIA,
  nivelLluvia,
  nombreCultivoMagyp,
  nombreMes,
  nombreMesCorto,
  textoDesvio,
  type HistoricalMetricId,
} from '../data/historicalData'
import type { CampanaHistorial, HistorialResponse } from '../types/api'
import { formatQq } from '../utils/formatters'
import { diaMes } from '../utils/lenguajeProductor'
import { AvisoEstadoDatos, type EstadoDatos } from './AvisoEstadoDatos'

interface HistoricalPanelProps {
  loteLabel: string
  historial: HistorialResponse | null
  cargando: boolean
  aviso: EstadoDatos | null
  onReintentar: () => void
  selectedYear: number | null
  selectedMetric: HistoricalMetricId
  onChangeYear: (anio: number) => void
  onChangeMetric: (metric: HistoricalMetricId) => void
  /** Nombre legible de un cultivo del catálogo del front (campañas guardadas del lote). */
  nombreCultivo: (id: string) => string
}

function claseDesvio(pct: number | null): string {
  if (pct == null || Math.abs(pct) <= 5) return 'hist-desvio neutro'
  return pct > 0 ? 'hist-desvio bueno' : 'hist-desvio malo'
}

/** Barras por campaña con la línea de lo normal (SVG propio, sin librerías). */
function GraficoCampanas({
  campanas,
  valor,
  normal,
  unidad,
  colorDe,
  seleccionada,
  onSeleccionar,
  titulo,
}: {
  campanas: CampanaHistorial[]
  valor: (c: CampanaHistorial) => number | null
  normal: number | null
  unidad: string
  colorDe: (c: CampanaHistorial) => string
  seleccionada: number | null
  onSeleccionar: (anio: number) => void
  titulo: string
}) {
  const ancho = 320
  const alto = 120
  const izq = 28
  const abajo = 16
  const valores = campanas.map(valor).filter((v): v is number => v != null)
  const max = Math.max(...valores, normal ?? 0, 1) * 1.08
  const paso = (ancho - izq) / Math.max(campanas.length, 1)
  const y = (v: number) => (alto - abajo) * (1 - v / max)
  return (
    <svg className="hist-grafico" viewBox={`0 0 ${ancho} ${alto}`} role="img" aria-label={titulo}>
      <text className="seg-eje" x={0} y={y(max / 1.08) + 8}>{Math.round(max / 1.08)}</text>
      <text className="seg-eje" x={0} y={alto - abajo}>0</text>
      {campanas.map((c, i) => {
        const v = valor(c)
        const x = izq + i * paso
        const sel = c.anio === seleccionada
        return (
          <g key={c.anio} onClick={() => onSeleccionar(c.anio)} className="hist-barra-g">
            {v != null && (
              <rect
                className={`hist-barra ${sel ? 'seleccionada' : ''} ${c.completa ? '' : 'parcial'}`}
                x={x + paso * 0.15}
                y={y(v)}
                width={paso * 0.7}
                height={Math.max(1, alto - abajo - y(v))}
                style={{ fill: colorDe(c) }}
              >
                <title>{`${c.etiqueta}: ${v} ${unidad}${c.completa ? '' : ' (campaña en curso)'}`}</title>
              </rect>
            )}
            {(i % 3 === 0 || sel) && (
              <text className={`seg-eje ${sel ? 'hist-eje-sel' : ''}`} x={x + paso / 2} y={alto - 3} textAnchor="middle">
                {String(c.anio).slice(2)}
              </text>
            )}
          </g>
        )
      })}
      {normal != null && (
        <line className="seg-habitual" x1={izq} x2={ancho} y1={y(normal)} y2={y(normal)}>
          <title>{`Normal: ${normal} ${unidad}`}</title>
        </line>
      )}
    </svg>
  )
}

const COLOR_NIVEL: Record<string, string> = {
  muy_seca: 'var(--color-risk-critical)',
  seca: 'var(--color-heat-soil)',
  normal: 'var(--color-water-rain-light)',
  humeda: 'var(--color-water-rain)',
  muy_humeda: 'var(--color-water-rain-dark)',
}

function RindeZona({ c }: { c: CampanaHistorial }) {
  if (c.rinde_zona.length === 0) {
    return (
      <p className="hist-nota">
        {c.completa
          ? 'Todavía no hay rindes publicados por el Ministerio de Agricultura para esta campaña en la zona.'
          : 'La campaña está en curso: el rinde de la zona se publica después de la cosecha.'}
      </p>
    )
  }
  return (
    <table className="hist-tabla">
      <thead>
        <tr>
          <th scope="col">Cultivo</th>
          <th scope="col">Rinde de la zona</th>
          <th scope="col">Contra lo normal</th>
        </tr>
      </thead>
      <tbody>
        {c.rinde_zona.map((r) => (
          <tr key={r.cultivo}>
            <td>{nombreCultivoMagyp(r.cultivo)}</td>
            <td>{formatQq(r.rinde_kg_ha)}</td>
            <td className={claseDesvio(r.vs_normal_pct)}>{textoDesvio(r.vs_normal_pct) || '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function CosechasLote({ c, nombreCultivo }: { c: CampanaHistorial; nombreCultivo: (id: string) => string }) {
  if (c.cosechas_lote.length === 0) return <p className="hist-nota">Sin campañas guardadas en este lote.</p>
  return (
    <ul className="hist-cosechas">
      {c.cosechas_lote.map((x) => (
        <li key={x.id}>
          <strong>{nombreCultivo(x.cultivo)}</strong> · sembrado el {diaMes(x.fecha_siembra)}
          {x.en_curso
            ? ' · en curso'
            : `${x.fecha_cosecha ? ` · cosechado el ${diaMes(x.fecha_cosecha)}` : ''}${x.rinde_kg_ha != null ? ` · ${formatQq(x.rinde_kg_ha)}` : ''}`}
        </li>
      ))}
    </ul>
  )
}

export function HistoricalPanel({
  loteLabel,
  historial,
  cargando,
  aviso,
  onReintentar,
  selectedYear,
  selectedMetric,
  onChangeYear,
  onChangeMetric,
  nombreCultivo,
}: HistoricalPanelProps) {
  const [isPlaying, setIsPlaying] = useState<boolean>(false)
  const campanas = historial?.campanas ?? []
  const anios = campanas.map((c) => c.anio)
  const actual = campanas.find((c) => c.anio === selectedYear) ?? campanas[campanas.length - 1] ?? null
  const meta = HISTORICAL_METRICS.find((m) => m.id === selectedMetric) ?? HISTORICAL_METRICS[0]
  const normales = historial?.normales

  // Reproducción automática campaña por campaña, sincronizada con el mapa
  useEffect(() => {
    if (!isPlaying || anios.length === 0) return
    const timer = window.setInterval(() => {
      const idx = anios.indexOf(selectedYear ?? anios[0])
      onChangeYear(anios[(idx + 1) % anios.length])
    }, 1400)
    return () => window.clearInterval(timer)
  }, [isPlaying, selectedYear, onChangeYear, anios])

  const seleccionar = (anio: number) => {
    setIsPlaying(false)
    onChangeYear(anio)
  }

  const nivel = actual ? nivelLluvia(actual.lluvia_vs_normal_pct) : null

  return (
    <>
      <section className="panel-section historical-controls-section">
        <div className="section-header-row">
          <div>
            <h2 className="section-title">Información histórica</h2>
            <p className="telemetry-lote-subtitle">{loteLabel}</p>
          </div>
          {actual && <span className="historical-year-hero-badge">{actual.etiqueta}</span>}
        </div>

        {aviso && <AvisoEstadoDatos estado={aviso} onReintentar={onReintentar} />}
        {cargando && !historial && <p className="seg-cargando">Consultando 20 campañas de datos satelitales…</p>}

        {campanas.length > 0 && (
          <>
            <div className="year-timeline-box">
              <div className="year-timeline-header">
                <div className="year-timeline-label">
                  <Calendar size={14} />
                  <span>
                    Campaña (julio a junio): <strong>{actual?.etiqueta}</strong>
                  </span>
                </div>
                <button type="button" className="play-timeline-btn" onClick={() => setIsPlaying((p) => !p)}>
                  {isPlaying ? <Pause size={14} /> : <Play size={14} />}
                  <span>{isPlaying ? 'Pausar' : 'Reproducir serie'}</span>
                </button>
              </div>
              <input
                type="range"
                className="ag-range year-range"
                aria-label={`Seleccionar campaña entre ${campanas[0].etiqueta} y ${campanas[campanas.length - 1].etiqueta}`}
                min={anios[0]}
                max={anios[anios.length - 1]}
                step={1}
                value={actual?.anio ?? anios[anios.length - 1]}
                onChange={(e) => seleccionar(Number(e.target.value))}
              />
            </div>

            <div className="control-group">
              <label className="control-label" htmlFor="historical-metric-select">
                <span>Dato histórico a visualizar</span>
              </label>
              <select
                id="historical-metric-select"
                className="ag-select"
                value={selectedMetric}
                onChange={(e) => onChangeMetric(e.target.value as HistoricalMetricId)}
              >
                {HISTORICAL_METRICS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
              <p className="what-if-helper-text">{meta.helperText}</p>
            </div>
          </>
        )}
      </section>

      {actual && (
        <section className="panel-section historical-series-section">
          <div className="selected-year-summary-card">
            <span className="winner-kicker">Campaña {actual.etiqueta}{actual.completa ? '' : ' (en curso)'}</span>
            <h3 className="selected-year-crop-title">
              {nivel ? TEXTO_NIVEL_LLUVIA[nivel] : 'Campaña en curso'}
            </h3>

            <div className="selected-year-kpis">
              <div className="year-kpi-item water">
                <CloudRain size={15} />
                <div>
                  <span className="year-kpi-label">Lluvia</span>
                  <strong className="year-kpi-val water">
                    {actual.lluvia_mm != null ? `${actual.lluvia_mm} mm` : '—'}
                    {actual.lluvia_vs_normal_pct != null && (
                      <span className={claseDesvio(actual.lluvia_vs_normal_pct)}>
                        {' '}
                        {textoDesvio(actual.lluvia_vs_normal_pct)}
                      </span>
                    )}
                  </strong>
                  <span className="hist-kpi-sub">
                    {actual.completa
                      ? `Lo normal es ${normales?.lluvia_mm ?? '—'} mm`
                      : actual.lluvia_comparada_hasta
                        ? `Hasta ahora. De julio a ${nombreMesCorto(actual.lluvia_comparada_hasta)}, contra lo normal de esos meses.`
                        : 'Hasta ahora (todavía sin un mes completo para comparar).'}
                  </span>
                </div>
              </div>

              <div className="year-kpi-item soil">
                <Droplets size={15} />
                <div>
                  <span className="year-kpi-label">Agua en las raíces</span>
                  <strong className="year-kpi-val water">
                    {actual.agua_raices_promedio_pct != null ? `${actual.agua_raices_promedio_pct}% promedio` : '—'}
                  </strong>
                  {actual.mes_mas_seco && (
                    <span className="hist-kpi-sub">
                      Mes más seco: {nombreMes(actual.mes_mas_seco)}, {actual.agua_raices_mes_mas_seco_pct}% (lo normal
                      ese mes es {actual.agua_raices_mes_mas_seco_normal_pct}%)
                    </span>
                  )}
                </div>
              </div>

              <div className="year-kpi-item soil">
                <Sprout size={15} />
                <div>
                  <span className="year-kpi-label">Este lote</span>
                  <CosechasLote c={actual} nombreCultivo={nombreCultivo} />
                </div>
              </div>
            </div>

            <span className="detail-section-subtitle">
              Cómo le fue a la zona
              {historial?.departamento_referencia
                ? ` (${historial.departamento_referencia.nombre}, ${historial.departamento_referencia.provincia})`
                : ''}
            </span>
            <RindeZona c={actual} />
          </div>

          {selectedMetric === 'lluvias' && (
            <GraficoCampanas
              campanas={campanas}
              valor={(c) => c.lluvia_mm}
              normal={normales?.lluvia_mm ?? null}
              unidad="mm"
              colorDe={(c) => COLOR_NIVEL[nivelLluvia(c.lluvia_vs_normal_pct) ?? 'normal']}
              seleccionada={actual.anio}
              onSeleccionar={seleccionar}
              titulo="Lluvia por campaña contra lo normal"
            />
          )}
          {selectedMetric === 'suelo' && (
            <GraficoCampanas
              campanas={campanas}
              valor={(c) => c.agua_raices_promedio_pct}
              normal={normales?.agua_raices_pct ?? null}
              unidad="% de agua en raíces (promedio; el color marca el bache del mes más seco)"
              colorDe={(c) => {
                const d = (c.agua_raices_mes_mas_seco_pct ?? 0) - (c.agua_raices_mes_mas_seco_normal_pct ?? 0)
                return d <= -8 ? 'var(--color-heat-soil)' : d <= -3 ? 'var(--color-gold-yellow)' : 'var(--color-water-rain)'
              }}
              seleccionada={actual.anio}
              onSeleccionar={seleccionar}
              titulo="Agua en las raíces por campaña; en naranja, las campañas con un mes muy seco"
            />
          )}
          {selectedMetric === 'cultivos' && (
            <div className="historical-timeline-list">
              {[...campanas].reverse().map((c) => {
                const zona = c.rinde_zona
                  .filter((r) => r.vs_normal_pct != null)
                  .slice(0, 3)
                  .map((r) => `${nombreCultivoMagyp(r.cultivo)} ${textoDesvio(r.vs_normal_pct)}`)
                  .join(' · ')
                return (
                  <button
                    key={c.anio}
                    type="button"
                    className={`historical-row-btn ${c.anio === actual.anio ? 'selected' : ''}`}
                    onClick={() => seleccionar(c.anio)}
                  >
                    <div className="hist-row-left">
                      <span className="hist-year-tag">{c.etiqueta}</span>
                      <div className="hist-crop-stack">
                        <strong className="hist-crop-main">
                          {c.cosechas_lote.length > 0
                            ? c.cosechas_lote.map((x) => nombreCultivo(x.cultivo)).join(' → ')
                            : 'Sin registro en el lote'}
                        </strong>
                        <span className="hist-crop-winter">{zona ? `Zona: ${zona}` : 'Sin rindes de la zona'}</span>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}

          <p className="rr-pie">
            <Info size={12} aria-hidden="true" /> {historial?.advertencias.join(' ')} Rinde de la zona: Ministerio de
            Agricultura (MAGyP), promedio del departamento.
          </p>
        </section>
      )}
    </>
  )
}
