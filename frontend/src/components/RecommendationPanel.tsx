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
import { THEME_COLORS } from '../theme/mapColors'
import type {
  CultivoId,
  RankingCultivoItem,
  RecomendacionPrincipal,
  RiesgoNivel,
} from '../types/api'
import { humanizeAgronomicWarnings } from '../utils/formatters'

interface RecommendationPanelProps {
  recomendacion: RecomendacionPrincipal | null
  ranking: RankingCultivoItem[]
  advertencias?: readonly string[]
  isWhatIfActive?: boolean
  errorMessage?: string | null
  onRetry?: () => void
}

function getCultivoDisplayName(idOrRaw: string): string {
  return (
    CULTIVOS_CATALOGO[idOrRaw as CultivoId]?.nombre ??
    idOrRaw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  )
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

export function RecommendationPanel({
  recomendacion,
  ranking,
  advertencias = [],
  isWhatIfActive = false,
  errorMessage = null,
  onRetry,
}: RecommendationPanelProps) {
  const [expandedCropId, setExpandedCropId] = useState<string | null>(null)
  const [moreOpenCropId, setMoreOpenCropId] = useState<string | null>(null)
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

  // Parámetros del anillo SVG del Puntaje general
  const radius = 34
  const circumference = 2 * Math.PI * radius

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

            const waterScore = Math.round(
              item.sub_scores?.hidroclimatico ??
                (isRecommended ? recomendacion.sub_scores.hidroclimatico : roundedScore)
            )
            const soilScore = Math.round(
              item.sub_scores?.suelo ??
                (isRecommended ? recomendacion.sub_scores.suelo : roundedScore)
            )
            const strokeDashoffset =
              circumference - (Math.min(100, roundedScore) / 100) * circumference

            const headlineReason = isRecommended
              ? (recomendacion.factores_clave_ml[0] ??
                'Mayor aptitud frente a la disponibilidad hídrica del lote y el balance del suelo.')
              : cropMeta
                ? `${cropMeta.aporteCarbonoLabel} · Demanda hídrica: ${cropMeta.demandaHidricaLabel}.`
                : `Aptitud combinada de ${roundedScore} puntos sobre 100 para las condiciones actuales del lote.`

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
                      <span className={riskInfo.className}>
                        {item.riesgo === 'critico' ? (
                          <ShieldAlert size={12} />
                        ) : item.riesgo === 'alto' ? (
                          <AlertTriangle size={12} />
                        ) : null}
                        <span>{riskInfo.label}</span>
                      </span>
                    </div>
                    <div className="ranking-score-right">
                      <strong className="ranking-total-score">
                        {roundedScore} / 100
                      </strong>
                      {isExpanded ? (
                        <ChevronUp size={14} aria-hidden="true" />
                      ) : (
                        <ChevronDown size={14} aria-hidden="true" />
                      )}
                    </div>
                  </div>

                  <div className="ranking-bar-track">
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

                      {/* ANILLO SVG DE PUNTAJE GENERAL */}
                      <div
                        className="score-ring-box"
                        title="Puntaje general (combina aptitud hidroclimática y aporte al suelo según el objetivo)"
                      >
                        <svg width="86" height="86" viewBox="0 0 86 86">
                          <circle
                            cx="43"
                            cy="43"
                            r={radius}
                            fill="none"
                            stroke={THEME_COLORS.primarySoft}
                            strokeWidth="7"
                          />
                          <circle
                            cx="43"
                            cy="43"
                            r={radius}
                            fill="none"
                            stroke={THEME_COLORS.primary}
                            strokeWidth="7"
                            strokeLinecap="round"
                            strokeDasharray={circumference}
                            strokeDashoffset={strokeDashoffset}
                            transform="rotate(-90 43 43)"
                          />
                        </svg>
                        <div className="score-ring-text">
                          <span className="score-ring-number">
                            {roundedScore}
                          </span>
                          <span className="score-ring-unit">/ 100</span>
                        </div>
                      </div>
                    </div>

                    {/* 2 BARRAS DE PILARES: AGUA/CLIMA (AZUL) Y SUELO (NARANJA) */}
                    <div className="pillars-breakdown">
                      <div className="pillar-item">
                        <div className="pillar-label-row">
                          <span>Aptitud frente al agua y el clima</span>
                          <strong className="pillar-score water">
                            {waterScore} / 100
                          </strong>
                        </div>
                        <div className="progress-track water-track">
                          <div
                            className="progress-fill water-fill"
                            style={{
                              width: `${Math.min(100, waterScore)}%`,
                            }}
                          />
                        </div>
                      </div>

                      <div className="pillar-item">
                        <div className="pillar-label-row">
                          <span>Aporte al suelo y la rotación</span>
                          <strong className="pillar-score heat">
                            {soilScore} / 100
                          </strong>
                        </div>
                        <div className="progress-track heat-track">
                          <div
                            className="progress-fill heat-fill"
                            style={{
                              width: `${Math.min(100, soilScore)}%`,
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
                        {isMoreOpen ? '− Menos' : '+ Mas...'}
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
                              : `${cropName} obtiene ${waterScore} puntos en aptitud hidroclimática y ${soilScore} puntos en aporte al suelo/rotación, ubicándose en la posición #${idx + 1} con ${riskInfo.label.toLowerCase()}.`}
                          </p>
                        </div>
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
