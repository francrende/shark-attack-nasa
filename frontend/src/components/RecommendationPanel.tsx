import {
  AlertTriangle,
  Award,
  BarChart3,
  CheckCircle2,
  GitCommitHorizontal,
  Info,
  ShieldAlert,
} from 'lucide-react'
import { CULTIVOS_CATALOGO } from '../data/demoFields'
import type {
  CultivoId,
  RankingCultivoItem,
  RecomendacionPrincipal,
  RiesgoNivel,
} from '../types/api'

interface RecommendationPanelProps {
  recomendacion: RecomendacionPrincipal
  ranking: RankingCultivoItem[]
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
      return { label: 'Riesgo Bajo', className: 'risk-badge low' }
    case 'medio':
      return { label: 'Riesgo Medio', className: 'risk-badge medium' }
    case 'alto':
      return { label: 'Riesgo Alto', className: 'risk-badge high' }
    case 'critico':
      return { label: 'Riesgo Crítico', className: 'risk-badge critical' }
  }
}

export function RecommendationPanel({
  recomendacion,
  ranking,
}: RecommendationPanelProps) {
  const winnerName = getCultivoDisplayName(recomendacion.cultivo)
  const winnerMeta = CULTIVOS_CATALOGO[recomendacion.cultivo as CultivoId]

  // Parámetros del anillo SVG del Score Final
  const radius = 38
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset =
    circumference - (Math.min(100, recomendacion.score_final) / 100) * circumference

  return (
    <section className="panel-section recommendation-section">
      <div className="section-header-row">
        <div>
          <span className="section-eyebrow">
            <Award size={13} />
            <span>PASO 3 · DECISIÓN AGRONÓMICA EXPLICADA (ML + MCDA)</span>
          </span>
          <h2 className="section-title">Recomendación y Ranking</h2>
        </div>
      </div>

      {/* TARJETA DESTACADA DEL CULTIVO GANADOR */}
      <div className="winner-card">
        <div className="winner-top-row">
          <div className="winner-main-info">
            <span className="winner-kicker">CULTIVO ÓPTIMO RECOMENDADO</span>
            <h3 className="winner-crop-name">{winnerName}</h3>
            {winnerMeta && (
              <p className="winner-crop-subtitle">
                {winnerMeta.aporteCarbonoLabel} · Demanda hídrica:{' '}
                <strong>{winnerMeta.demandaHidricaLabel}</strong>
              </p>
            )}
          </div>

          {/* ANILLO SVG DE SCORE FINAL */}
          <div className="score-ring-box">
            <svg width="96" height="96" viewBox="0 0 96 96">
              <circle
                cx="48"
                cy="48"
                r={radius}
                fill="none"
                stroke="rgba(75, 91, 45, 0.16)"
                strokeWidth="8"
              />
              <circle
                cx="48"
                cy="48"
                r={radius}
                fill="none"
                stroke="#4B5B2D"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                transform="rotate(-90 48 48)"
              />
            </svg>
            <div className="score-ring-text">
              <span className="score-ring-number">
                {recomendacion.score_final}
              </span>
              <span className="score-ring-unit">PTS</span>
            </div>
          </div>
        </div>

        {/* DESGLOSE DE LOS 2 PILARES: HIDROCLIMÁTICO (#4A7B9D) VS SUELO (#F05D23) */}
        <div className="pillars-breakdown">
          <div className="pillar-item">
            <div className="pillar-label-row">
              <span>Aptitud frente al Agua y Clima</span>
              <strong className="pillar-score water">
                {recomendacion.sub_scores.hidroclimatico} / 100
              </strong>
            </div>
            <div className="progress-track water-track">
              <div
                className="progress-fill water-fill"
                style={{
                  width: `${Math.min(100, recomendacion.sub_scores.hidroclimatico)}%`,
                }}
              />
            </div>
          </div>

          <div className="pillar-item">
            <div className="pillar-label-row">
              <span>Aporte al Suelo y Rotación</span>
              <strong className="pillar-score heat">
                {recomendacion.sub_scores.suelo} / 100
              </strong>
            </div>
            <div className="progress-track heat-track">
              <div
                className="progress-fill heat-fill"
                style={{
                  width: `${Math.min(100, recomendacion.sub_scores.suelo)}%`,
                }}
              />
            </div>
          </div>
        </div>

        {/* SECUENCIA ANUAL SUGERIDA (INVIERNO -> VERANO) */}
        <div className="sequence-banner">
          <div className="sequence-icon">
            <GitCommitHorizontal size={18} />
          </div>
          <div>
            <span className="sequence-label">
              Secuencia Anual Sugerida (Invierno → Verano)
            </span>
            <strong className="sequence-value">
              {recomendacion.secuencia_sugerida}
            </strong>
          </div>
        </div>

        {/* FACTORES CLAVE ML */}
        <div className="ml-factors-list">
          {recomendacion.factores_clave_ml.map((factor, idx) => (
            <div key={idx} className="ml-factor-item">
              <CheckCircle2 size={14} className="ml-factor-icon" />
              <span>{factor}</span>
            </div>
          ))}
        </div>

        {/* EXPLICACIÓN TRANSPARENTE */}
        <div className="explanation-callout">
          <Info size={16} className="explanation-icon" />
          <p>{recomendacion.explicacion}</p>
        </div>
      </div>

      {/* GRÁFICO DE BARRAS COMPARATIVO: RANKING DE CULTIVOS DE LA CAMPAÑA */}
      <div className="ranking-box">
        <div className="ranking-header">
          <div className="ranking-title">
            <BarChart3 size={16} />
            <span>Comparativa de Cultivos Candidatos</span>
          </div>
          <div className="ranking-legend">
            <span className="legend-dot water" />
            <span>Hidroclimático</span>
            <span className="legend-dot heat" />
            <span>Suelo</span>
          </div>
        </div>

        <div className="ranking-list">
          {ranking.map((item, idx) => {
            const cropName = getCultivoDisplayName(item.cultivo)
            const riskInfo = getRiskLabelAndClass(item.riesgo)
            const isTop = idx === 0

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
                    {item.score_final} pts
                  </strong>
                </div>

                {/* Barra principal de Score Final */}
                <div className="ranking-bar-track">
                  <div
                    className={`ranking-bar-fill ${isTop ? 'winner-bar' : 'standard-bar'}`}
                    style={{
                      width: `${Math.min(100, Math.max(6, item.score_final))}%`,
                    }}
                  />
                </div>

                {/* Sub-barras gemelas si están presentes */}
                {item.sub_scores && (
                  <div className="ranking-subscores-row">
                    <span className="subscore-pill water">
                      Clima/Agua: <strong>{item.sub_scores.hidroclimatico}%</strong>
                    </span>
                    <span className="subscore-pill heat">
                      Suelo/Rotación: <strong>{item.sub_scores.suelo}%</strong>
                    </span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
