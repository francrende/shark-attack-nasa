import { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Info,
  Lock,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react'
import { CULTIVOS_CATALOGO } from '../data/demoFields'
import type {
  CultivoId,
  DepartamentoReferencia,
  FaseEnso,
  RankingCultivoItem,
  RecomendacionPrincipal,
  RiesgoNivel,
} from '../types/api'
import { humanizeAgronomicWarnings } from '../utils/formatters'
import { formatQq } from '../utils/formatters'
import {
  textoAporteSuelo,
  textoDesvioNormal,
  textoRiesgoAnioMalo,
} from '../utils/lenguajeProductor'
import { RiesgoRindeResumen } from './RiesgoRindeResumen'

interface RecommendationPanelProps {
  recomendacion: RecomendacionPrincipal | null
  ranking: RankingCultivoItem[]
  advertencias?: readonly string[]
  isWhatIfActive?: boolean
  errorMessage?: string | null
  onRetry?: () => void
  /** BACK-27: fase ENSO de los años con los que se compara. */
  faseEnso?: FaseEnso | null
  /** ML-17: departamento cuyo rinde normal es la referencia. */
  departamento?: DepartamentoReferencia | null
}

function getCultivoDisplayName(idOrRaw: string): string {
  return (
    CULTIVOS_CATALOGO[idOrRaw as CultivoId]?.nombre ??
    idOrRaw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  )
}

function esCobertura(cultivo: string): boolean {
  return cultivo.endsWith('_cobertura')
}

function getRiskLabelAndClass(riesgo: RiesgoNivel): {
  label: string
  className: string
} {
  switch (riesgo) {
    case 'bajo':
      return { label: 'Riesgo bajo', className: 'risk-badge low' }
    case 'medio':
      return { label: 'Riesgo medio', className: 'risk-badge medium' }
    case 'alto':
      return { label: 'Riesgo alto', className: 'risk-badge high' }
    case 'critico':
      return { label: 'Riesgo muy alto', className: 'risk-badge critical' }
  }
}

/** Fila compacta: "34 qq/ha · 3 de cada 10 con rinde bajo" (o lo que haya disponible). */
function resumenCompacto(item: RankingCultivoItem, nombre: string, hidro: number): string {
  const partes: string[] = []
  const esperado = item.rinde_kg_ha?.esperado
  if (esperado != null) partes.push(formatQq(esperado))
  const riesgo = textoRiesgoAnioMalo(item, nombre)
  if (riesgo) partes.push(riesgo.corto)
  if (partes.length === 0) partes.push(textoDesvioNormal(hidro).texto)
  return partes.join(' · ')
}

function porcentaje(p: number | null | undefined): string {
  return p == null ? '—' : `${Math.round(p * 100)}%`
}

function kg(v: number | null | undefined): string {
  return v == null ? '—' : `${Math.round(v).toLocaleString('es-AR')} kg/ha`
}

function DetalleTecnico({
  item,
  departamento,
}: {
  item: RankingCultivoItem
  departamento?: DepartamentoReferencia | null
}) {
  const r = item.rinde_kg_ha
  const filas: [string, string][] = [
    ['Probabilidad de año malo', porcentaje(item.prob_anio_malo)],
    ['Probabilidad típica del cultivo', porcentaje(item.prob_anio_malo_tipica)],
    [
      'Anticipa diferencias entre años',
      item.anticipa_diferencias == null ? '—' : item.anticipa_diferencias ? 'Sí' : 'No',
    ],
    ['Rinde esperado', kg(r?.esperado)],
    ['Rinde en un año malo / bueno', `${kg(r?.anio_malo)} / ${kg(r?.anio_bueno)}`],
    ['Rinde normal del departamento', kg(r?.normal)],
    ['Puntaje combinado (objetivo elegido)', `${Math.round(item.score_final)}`],
    [
      'Puntaje agua y clima / suelo',
      `${item.sub_scores ? Math.round(item.sub_scores.hidroclimatico) : '—'} / ${item.sub_scores ? Math.round(item.sub_scores.suelo) : '—'}`,
    ],
    [
      'Puntaje en año malo / bueno (con error real)',
      `${item.puntaje_anio_malo ?? '—'} / ${item.puntaje_anio_bueno ?? '—'}`,
    ],
    ['P10 del clima de los años comparados', `${item.score_hidroclimatico_p10 ?? '—'}`],
    [
      'Años comparados / desfavorables',
      `${item.anios_evaluados ?? '—'} / ${item.anios_desfavorables ?? '—'}`,
    ],
    [
      'Departamento de referencia',
      departamento
        ? `${departamento.codigo} · ${departamento.nombre} (${Math.round(departamento.distancia_km)} km)`
        : '—',
    ],
  ]
  return (
    <table className="detalle-tecnico-tabla">
      <tbody>
        {filas.map(([k, v]) => (
          <tr key={k}>
            <th scope="row">{k}</th>
            <td>{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function RecommendationPanel({
  recomendacion,
  ranking,
  advertencias = [],
  isWhatIfActive = false,
  errorMessage = null,
  onRetry,
  faseEnso,
  departamento,
}: RecommendationPanelProps) {
  const [expandedCropId, setExpandedCropId] = useState<string | null>(null)
  const [moreOpenCropId, setMoreOpenCropId] = useState<string | null>(null)
  const [tecnicoOpenCropId, setTecnicoOpenCropId] = useState<string | null>(null)
  const [showAllCrops, setShowAllCrops] = useState<boolean>(false)

  if (errorMessage || !recomendacion) {
    return (
      <section
        className="panel-section recommendation-section"
        aria-live="polite"
      >
        <div className="section-header-row">
          <div>
            <h2 className="section-title">Estrategia de rotación</h2>
          </div>
        </div>
        <div className="telemetry-error-box" role="alert">
          <AlertTriangle size={16} aria-hidden="true" />
          <div className="telemetry-error-content">
            <strong>Ocurrió un error inesperado</strong>
            <p>
              {errorMessage && errorMessage !== 'Ocurrió un error inesperado'
                ? errorMessage
                : 'No fue posible completar la simulación para el campo seleccionado.'}
            </p>
          </div>
          {onRetry && (
            <button
              type="button"
              className="recommendation-retry-btn"
              onClick={onRetry}
            >
              <RefreshCw size={13} aria-hidden="true" />
              <span>Reintentar</span>
            </button>
          )}
        </div>
      </section>
    )
  }

  // Solo se rankean los cultivos que hoy se pueden sembrar; el resto se agrupa por motivo debajo.
  const sembrables = ranking.filter((item) => !item.motivo_no_sembrable)
  const noSembrablesPorMotivo = ranking.reduce<Map<string, string[]>>((grupos, item) => {
    if (item.motivo_no_sembrable) {
      const cultivos = grupos.get(item.motivo_no_sembrable) ?? []
      cultivos.push(getCultivoDisplayName(item.cultivo))
      grupos.set(item.motivo_no_sembrable, cultivos)
    }
    return grupos
  }, new Map())

  // Anti-clutter: mostrar Top 3 por defecto
  const visibleRanking = showAllCrops ? sembrables : sembrables.slice(0, 3)
  const safeAdvertencias = humanizeAgronomicWarnings([advertencias])

  const handleToggleCrop = (cultivoId: string) => {
    setExpandedCropId((prev) => (prev === cultivoId ? null : cultivoId))
    if (moreOpenCropId && moreOpenCropId !== cultivoId) {
      setMoreOpenCropId(null)
    }
  }

  return (
    <section
      className="panel-section recommendation-section"
      aria-live="polite"
    >
      <div className="section-header-row">
        <div>
          <h2 className="section-title">Estrategia de rotación</h2>
        </div>
        {isWhatIfActive && (
          <span className="what-if-active-pill">Escenario simulado</span>
        )}
      </div>

      {safeAdvertencias.length > 0 && (
        <div className="telemetry-warning-banner" role="status">
          <AlertTriangle size={15} aria-hidden="true" />
          <div className="telemetry-warning-list">
            {safeAdvertencias.map((adv, idx) => (
              <span key={`${idx}-${adv}`}>{adv}</span>
            ))}
          </div>
        </div>
      )}

      {/* LISTADO ÚNICO INTERACTIVO: AL TOCAR CUALQUIER CULTIVO SE EXPANDE SU CARD COMPLETA */}
      <div className="ranking-box">
        <div className="ranking-list">
          {visibleRanking.map((item, idx) => {
            const cropName = getCultivoDisplayName(item.cultivo)
            const cropMeta = CULTIVOS_CATALOGO[item.cultivo as CultivoId]
            const riskInfo = getRiskLabelAndClass(item.riesgo)
            const isTop = idx === 0
            const isRecommended = item.cultivo === recomendacion.cultivo
            const roundedScore = Math.round(item.score_final)
            const isExpanded = expandedCropId === item.cultivo
            const isMoreOpen = moreOpenCropId === item.cultivo
            const isTecnicoOpen = tecnicoOpenCropId === item.cultivo

            const waterScore =
              item.sub_scores?.hidroclimatico ??
              (isRecommended ? recomendacion.sub_scores.hidroclimatico : item.score_final)
            const soilScore =
              item.sub_scores?.suelo ??
              (isRecommended ? recomendacion.sub_scores.suelo : item.score_final)
            const aporteSuelo = textoAporteSuelo(soilScore)
            // Si no hay probabilidad publicada, el badge de categoría sigue siendo la referencia.
            const tieneFrecuencia = item.prob_anio_malo_tipica != null

            const headlineReason = isRecommended
              ? (recomendacion.factores_clave_ml[0] ??
                'Mayor aptitud frente a la disponibilidad hídrica del lote y el balance del suelo.')
              : cropMeta
                ? `${cropMeta.aporteCarbonoLabel} · Demanda hídrica: ${cropMeta.demandaHidricaLabel}.`
                : `Puesto #${idx + 1} para las condiciones actuales del lote.`

            return (
              <div
                key={item.cultivo}
                className={`ranking-row ${isTop ? 'top-rank' : ''} ${isExpanded ? 'expanded' : ''}`}
              >
                <button
                  type="button"
                  className="ranking-row-trigger"
                  aria-expanded={isExpanded}
                  onClick={() => handleToggleCrop(item.cultivo)}
                >
                  <div className="ranking-row-head">
                    <div className="ranking-crop-title">
                      <span className="rank-index">#{idx + 1}</span>
                      <strong>{cropName}</strong>
                      {!tieneFrecuencia && (
                        <span className={riskInfo.className}>
                          {item.riesgo === 'critico' ? (
                            <ShieldAlert size={12} />
                          ) : item.riesgo === 'alto' ? (
                            <AlertTriangle size={12} />
                          ) : null}
                          <span>{riskInfo.label}</span>
                        </span>
                      )}
                    </div>
                    <div className="ranking-score-right">
                      <span className="ranking-resumen-compacto">
                        {resumenCompacto(item, cropName, waterScore)}
                      </span>
                      {isExpanded ? (
                        <ChevronUp size={14} aria-hidden="true" />
                      ) : (
                        <ChevronDown size={14} aria-hidden="true" />
                      )}
                    </div>
                  </div>

                  <div
                    className="ranking-bar-track"
                    title="Posición relativa según el objetivo elegido (agua y clima + aporte al suelo)"
                  >
                    <div
                      className={`ranking-bar-fill ${isTop ? 'winner-bar' : 'standard-bar'}`}
                      style={{
                        width: `${Math.min(100, Math.max(6, roundedScore))}%`,
                      }}
                    />
                  </div>
                </button>

                {isExpanded && (
                  <div className="winner-card ranking-expanded-card">
                    <div className="winner-top-row">
                      <div className="winner-main-info">
                        <span className="winner-kicker">
                          {isRecommended
                            ? 'Cultivo recomendado'
                            : `Alternativa #${idx + 1}`}
                        </span>
                        <h3 className="winner-crop-name">{cropName}</h3>
                        <p className="winner-headline-reason">
                          {headlineReason}
                        </p>
                      </div>
                    </div>

                    <RiesgoRindeResumen
                      datos={item}
                      nombreCultivo={cropName}
                      esCobertura={esCobertura(item.cultivo)}
                      hidroclimatico={waterScore}
                      aniosEvaluados={item.anios_evaluados}
                      fase={faseEnso}
                      departamento={departamento}
                    />

                    <div className="pillars-breakdown">
                      <div className="pillar-item">
                        <div className="pillar-label-row">
                          <span>Aporte al suelo y la rotación</span>
                          <strong className={`pillar-score nivel-${aporteSuelo.nivel}`}>
                            {aporteSuelo.texto}
                          </strong>
                        </div>
                        <div className="progress-track heat-track">
                          <div
                            className="progress-fill heat-fill"
                            style={{
                              width: `${Math.min(100, Math.round(soilScore))}%`,
                            }}
                          />
                        </div>
                      </div>
                    </div>

                    {/* "+ Mas..." SIN CONTENEDOR EN ESQUINA INFERIOR DERECHA */}
                    <div className="winner-more-row">
                      <button
                        type="button"
                        className="detail-link-btn"
                        onClick={() =>
                          setMoreOpenCropId((prev) =>
                            prev === item.cultivo ? null : item.cultivo
                          )
                        }
                        aria-expanded={isMoreOpen}
                      >
                        {isMoreOpen ? '− Menos' : '+ Más...'}
                      </button>
                    </div>

                    {isMoreOpen && (
                      <div className="winner-detail-drawer">
                        {isRecommended && (
                          <>
                            <span className="detail-section-subtitle">
                              Factores determinantes del análisis
                            </span>
                            <div className="ml-factors-list">
                              {recomendacion.factores_clave_ml.map(
                                (factor, factorIdx) => (
                                  <div key={factorIdx} className="ml-factor-item">
                                    <CheckCircle2
                                      size={14}
                                      className="ml-factor-icon"
                                    />
                                    <span>{factor}</span>
                                  </div>
                                )
                              )}
                            </div>
                          </>
                        )}

                        {cropMeta && (
                          <p className="winner-crop-subtitle">
                            <strong>Aporte al lote:</strong>{' '}
                            {cropMeta.aporteCarbonoLabel} ·{' '}
                            <strong>Consumo de agua:</strong>{' '}
                            {cropMeta.demandaHidricaLabel}
                          </p>
                        )}

                        <div className="explanation-callout">
                          <Info size={16} className="explanation-icon" />
                          <p>
                            {isRecommended
                              ? recomendacion.explicacion
                              : `${cropName} queda en el puesto #${idx + 1}: ${resumenCompacto(item, cropName, waterScore)}; aporte al suelo ${aporteSuelo.texto.toLowerCase()}.`}
                          </p>
                        </div>

                        <button
                          type="button"
                          className="detail-link-btn detalle-tecnico-btn"
                          onClick={() =>
                            setTecnicoOpenCropId((prev) =>
                              prev === item.cultivo ? null : item.cultivo
                            )
                          }
                          aria-expanded={isTecnicoOpen}
                        >
                          {isTecnicoOpen ? '− Ocultar detalle técnico' : 'Ver detalle técnico'}
                        </button>
                        {isTecnicoOpen && <DetalleTecnico item={item} departamento={departamento} />}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {sembrables.length > 3 && (
          <button
            type="button"
            className="show-all-crops-btn"
            onClick={() => setShowAllCrops((prev) => !prev)}
          >
            <span>
              {showAllCrops
                ? 'Mostrar solo los 3 primeros'
                : `Ver todos los cultivos (${sembrables.length})`}
            </span>
            {showAllCrops ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>
        )}

        {noSembrablesPorMotivo.size > 0 && (
          <div className="unavailable-crops" role="note">
            <div className="unavailable-crops-head">
              <Lock size={13} aria-hidden="true" />
              <span>Cultivos no disponibles en este lote</span>
            </div>
            {[...noSembrablesPorMotivo.entries()].map(([motivo, cultivos]) => (
              <div key={motivo} className="unavailable-group">
                <div className="unavailable-chips">
                  {cultivos.map((nombre) => (
                    <span key={nombre} className="unavailable-chip">
                      {nombre}
                    </span>
                  ))}
                </div>
                <p className="unavailable-reason">{motivo}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
