import { useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  GitCommitHorizontal,
  Info,
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

interface RecommendationPanelProps {
  recomendacion: RecomendacionPrincipal
  ranking: RankingCultivoItem[]
  isWhatIfActive?: boolean
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
  isWhatIfActive = false,
}: RecommendationPanelProps) {
  const [showDetail, setShowDetail] = useState<boolean>(false)
  const [showAllCrops, setShowAllCrops] = useState<boolean>(false)

  const winnerName = getCultivoDisplayName(recomendacion.cultivo)
  const winnerMeta = CULTIVOS_CATALOGO[recomendacion.cultivo as CultivoId]

  const roundedFinalScore = Math.round(recomendacion.score_final)
  const roundedWaterScore = Math.round(recomendacion.sub_scores.hidroclimatico)
  const roundedSoilScore = Math.round(recomendacion.sub_scores.suelo)

  // Primera oración corta del fundamento como conclusión rápida (< 5s)
  const headlineReason =
    recomendacion.factores_clave_ml[0] ??
    'Presenta la mayor aptitud frente a la disponibilidad hídrica del lote y el balance del suelo.'

  // Parámetros del anillo SVG del Puntaje general
  const radius = 38
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset =
    circumference - (Math.min(100, roundedFinalScore) / 100) * circumference

  // Anti-clutter: mostrar Top 3 por defecto
  const visibleRanking = showAllCrops ? ranking : ranking.slice(0, 3)

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

      {/* 1. CONCLUSIÓN PRIMERO: CULTIVO GANADOR + PUNTAJE GENERAL + MOTIVO EN 1 LÍNEA */}
      <div className="winner-card">
        <div className="winner-top-row">
          <div className="winner-main-info">
            <span className="winner-kicker">Cultivo recomendado</span>
            <h3 className="winner-crop-name">{winnerName}</h3>
            <p className="winner-headline-reason">{headlineReason}</p>
          </div>

          {/* ANILLO SVG DE PUNTAJE GENERAL */}
          <div
            className="score-ring-box"
            title="Puntaje general (combina aptitud hidroclimática y aporte al suelo según la prioridad seleccionada)"
          >
            <svg width="96" height="96" viewBox="0 0 96 96">
              <circle
                cx="48"
                cy="48"
                r={radius}
                fill="none"
                stroke={THEME_COLORS.primarySoft}
                strokeWidth="8"
              />
              <circle
                cx="48"
                cy="48"
                r={radius}
                fill="none"
                stroke={THEME_COLORS.primary}
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                transform="rotate(-90 48 48)"
              />
            </svg>
            <div className="score-ring-text">
              <span className="score-ring-number">{roundedFinalScore}</span>
              <span className="score-ring-unit">/ 100</span>
            </div>
          </div>
        </div>

        {/* 2. EVIDENCIA EN 2 BARRAS: AGUA/CLIMA (AZUL) Y SUELO (NARANJA) */}
        <div className="pillars-breakdown">
          <div className="pillar-item">
            <div className="pillar-label-row">
              <span>Aptitud frente al agua y el clima</span>
              <strong className="pillar-score water">
                {roundedWaterScore} / 100
              </strong>
            </div>
            <div className="progress-track water-track">
              <div
                className="progress-fill water-fill"
                style={{
                  width: `${Math.min(100, roundedWaterScore)}%`,
                }}
              />
            </div>
          </div>

          <div className="pillar-item">
            <div className="pillar-label-row">
              <span>Aporte al suelo y la rotación</span>
              <strong className="pillar-score heat">
                {roundedSoilScore} / 100
              </strong>
            </div>
            <div className="progress-track heat-track">
              <div
                className="progress-fill heat-fill"
                style={{
                  width: `${Math.min(100, roundedSoilScore)}%`,
                }}
              />
            </div>
          </div>
        </div>

        {/* 3. ROTACIÓN SUGERIDA PARA EL AÑO */}
        <div className="sequence-banner">
          <div className="sequence-icon">
            <GitCommitHorizontal size={18} />
          </div>
          <div>
            <span className="sequence-label">
              Rotación sugerida para el año
            </span>
            <strong className="sequence-value">
              {recomendacion.secuencia_sugerida}
            </strong>
          </div>
        </div>

        {/* 4. DIVULGACIÓN PROGRESIVA: "VER DETALLE" */}
        <button
          type="button"
          className="detail-toggle-btn"
          onClick={() => setShowDetail((prev) => !prev)}
          aria-expanded={showDetail}
        >
          <span>
            {showDetail
              ? 'Ocultar fundamentos'
              : 'Ver fundamentos de la recomendación'}
          </span>
          {showDetail ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>

        {showDetail && (
          <div className="winner-detail-drawer">
            <span className="detail-section-subtitle">
              Factores determinantes del análisis
            </span>
            <div className="ml-factors-list">
              {recomendacion.factores_clave_ml.map((factor, idx) => (
                <div key={idx} className="ml-factor-item">
                  <CheckCircle2 size={14} className="ml-factor-icon" />
                  <span>{factor}</span>
                </div>
              ))}
            </div>

            {winnerMeta && (
              <p className="winner-crop-subtitle">
                <strong>Aporte al lote:</strong> {winnerMeta.aporteCarbonoLabel}{' '}
                · <strong>Consumo de agua:</strong>{' '}
                {winnerMeta.demandaHidricaLabel}
              </p>
            )}

            <div className="explanation-callout">
              <Info size={16} className="explanation-icon" />
              <p>{recomendacion.explicacion}</p>
            </div>
          </div>
        )}
      </div>

      {/* RANKING COMPARATIVO COMPACTO (TOP 3 POR DEFECTO + VER TODOS) */}
      <div className="ranking-box">
        <div className="ranking-header">
          <div className="ranking-title">
            <BarChart3 size={16} />
            <span>Comparativa de cultivos para esta campaña</span>
          </div>
          <span className="ranking-subtitle-hint">Puntaje sobre 100</span>
        </div>

        <div className="ranking-list">
          {visibleRanking.map((item, idx) => {
            const cropName = getCultivoDisplayName(item.cultivo)
            const riskInfo = getRiskLabelAndClass(item.riesgo)
            const isTop = idx === 0
            const roundedScore = Math.round(item.score_final)

            return (
              <div
                key={item.cultivo}
                className={`ranking-row ${isTop ? 'top-rank' : ''}`}
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
                  <strong className="ranking-total-score">
                    {roundedScore} / 100
                  </strong>
                </div>

                <div className="ranking-bar-track">
                  <div
                    className={`ranking-bar-fill ${isTop ? 'winner-bar' : 'standard-bar'}`}
                    style={{
                      width: `${Math.min(100, Math.max(6, roundedScore))}%`,
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>

        {ranking.length > 3 && (
          <button
            type="button"
            className="show-all-crops-btn"
            onClick={() => setShowAllCrops((prev) => !prev)}
          >
            <span>
              {showAllCrops
                ? 'Mostrar solo los 3 primeros'
                : `Ver todos los cultivos (${ranking.length})`}
            </span>
            {showAllCrops ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>
        )}
      </div>
    </section>
  )
}
