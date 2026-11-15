import { useState } from 'react'
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  CloudRain,
  Droplets,
  Flame,
  Layers,
  Loader2,
  MapPin,
  Mountain,
  RefreshCw,
  Sprout,
} from 'lucide-react'
import { CULTIVOS_CATALOGO } from '../data/demoFields'
import type {
  FieldCampaign,
  PerfilSuelo,
  PerfilSueloTelemetria,
  TelemetriaNasa,
  TelemetriaNasaInfo,
  TopografiaTelemetria,
} from '../types/api'
import {
  formatHumanDate,
  formatSignedAnomalyPct,
  humanizeAgronomicWarnings,
} from '../utils/formatters'

interface TelemetryCardsProps {
  loteLabel: string
  isFieldAssigned?: boolean
  telemetria: TelemetriaNasa | TelemetriaNasaInfo | null
  perfilSuelo: PerfilSuelo | PerfilSueloTelemetria | null
  topografia?: TopografiaTelemetria | null
  advertencias?: string[]
  latestCampaign?: FieldCampaign | null
  isLoading?: boolean
  errorMessage?: string | null
  onRetry?: () => void
  isWhatIfActive: boolean
  isRetryingFieldData?: boolean
}

function formatSoilTexture(textureRaw: string): string {
  const clean = textureRaw.replace(/_/g, ' ')
  return clean.charAt(0).toUpperCase() + clean.slice(1)
}

function formatCropName(cultivoRaw: string): string {
  const meta = (
    CULTIVOS_CATALOGO as Record<string, { nombre: string } | undefined>
  )[cultivoRaw]
  if (meta?.nombre) return meta.nombre
  return formatSoilTexture(cultivoRaw)
}

function formatLatestCampaign(campaign: FieldCampaign): string {
  const cropName = formatCropName(campaign.cultivo)
  const seasonLabel = campaign.campana === 'invierno' ? 'Invierno' : 'Verano'
  const dateLabel = formatHumanDate(campaign.fecha_inicio)
  const parts = [`${cropName} (${seasonLabel} · ${dateLabel})`]

  if (campaign.rinde_kg_ha !== null && campaign.rinde_kg_ha !== undefined) {
    parts.push(`Rinde: ${Math.round(campaign.rinde_kg_ha)} kg/ha`)
  }
  if (campaign.resultado_notas && campaign.resultado_notas.trim()) {
    parts.push(campaign.resultado_notas.trim())
  }

  return parts.join(' — ')
}

function formatRotationCondition(condRaw: string): string {
  const map: Record<string, string> = {
    deficit_rastrojo_por_soja:
      'Quedó poca cobertura después de la soja; conviene sumar raíces y rastrojo.',
    buena_cobertura_graminea:
      'Buena cobertura de rastrojo que ayuda a conservar la humedad.',
    suelo_enriquecido_en_nitrogeno:
      'Lote enriquecido en nitrógeno gracias al cultivo de cobertura previo.',
    alerta_extraccion_nutrientes:
      'Poca cobertura superficial; el suelo necesita reponer materia orgánica.',
    rotacion_equilibrada_oleaginosa:
      'Rotación equilibrada luego del cultivo anterior.',
  }
  return map[condRaw] ?? condRaw.replace(/_/g, ' ')
}

function getRootWaterMeaning(pct: number): string {
  if (pct < 38) return 'Reserva ajustada'
  if (pct < 55) return 'Reserva intermedia'
  return 'Buena reserva'
}

function getSurfaceWaterMeaning(pct: number): string {
  if (pct < 32) return 'Seco en superficie'
  if (pct < 52) return 'Humedad justa'
  return 'Óptimo para sembrar'
}

function getHeatRiskMeaning(riesgoRaw: string): {
  label: string
  percent: number
} {
  const lower = riesgoRaw.toLowerCase()
  if (lower === 'critico' || lower === 'extremo') {
    return { label: 'Riesgo muy alto', percent: 92 }
  }
  if (lower === 'alto') return { label: 'Riesgo alto', percent: 76 }
  if (lower === 'medio' || lower === 'moderado') {
    return { label: 'Riesgo medio', percent: 48 }
  }
  return { label: 'Riesgo bajo', percent: 24 }
}

const VAN_BEMMELEN_FACTOR = 1.724

function getOrganicMatterPct(
  perfilSuelo: PerfilSuelo | PerfilSueloTelemetria | null
): number | null {
  if (!perfilSuelo) return null
  if (
    perfilSuelo.materia_organica_g_kg !== null &&
    perfilSuelo.materia_organica_g_kg !== undefined
  ) {
    return perfilSuelo.materia_organica_g_kg / 10
  }
  if (
    perfilSuelo.carbono_organico_g_kg !== null &&
    perfilSuelo.carbono_organico_g_kg !== undefined
  ) {
    return (perfilSuelo.carbono_organico_g_kg * VAN_BEMMELEN_FACTOR) / 10
  }
  return null
}

function getOrganicMatterMeaning(moPct: number): string {
  if (moPct < 2.9) return 'Baja fertilidad'
  if (moPct < 3.5) return 'Nivel medio'
  return 'Suelo bien nutrido'
}

export function TelemetryCards({
  loteLabel,
  isFieldAssigned = false,
  telemetria,
  perfilSuelo,
  topografia = null,
  advertencias = [],
  latestCampaign = null,
  isLoading = false,
  errorMessage = null,
  onRetry,
  isWhatIfActive,
  isRetryingFieldData = false,
}: TelemetryCardsProps) {
  const [showSoilDetail, setShowSoilDetail] = useState<boolean>(false)

  const headerNode = (
    <div className="section-header-row campaign-header-row">
      <h2 className="section-title">Info general</h2>
      <span
        className={`campaign-field-tag ${!isFieldAssigned ? 'is-muted' : ''}`}
        title={isFieldAssigned ? `Campo activo: ${loteLabel}` : loteLabel}
      >
        <MapPin size={12} aria-hidden="true" />
        <span className="campaign-field-tag-name">{loteLabel}</span>
      </span>
    </div>
  )

    const hasSoilData =
      perfilSuelo !== null &&
      ((perfilSuelo.materia_organica_g_kg !== null &&
        perfilSuelo.materia_organica_g_kg !== undefined) ||
        perfilSuelo.carbono_organico_g_kg !== null ||
        Boolean(perfilSuelo.textura_predominante) ||
        ('arcilla_pct' in perfilSuelo && perfilSuelo.arcilla_pct !== null))

    const hasAnyData =
      telemetria !== null || hasSoilData || topografia !== null || latestCampaign !== null

    if (isLoading && !hasAnyData) {
      return (
        <section className="panel-section telemetry-section" aria-busy="true">
          {headerNode}
          <div className="skeleton-card" aria-label="Cargando telemetría del campo">
            <div className="skeleton-line short" />
            <div className="skeleton-line title" />
            <div className="skeleton-box" />
            <div className="skeleton-line" />
          </div>
        </section>
      )
    }

      if (!hasAnyData) {
        return (
          <section className="panel-section telemetry-section">
            {headerNode}
            <div className="telemetry-error-box">
              <AlertTriangle size={16} />
              <div className="telemetry-error-content">
                <strong>No se puede mostrar en este momento</strong>
                <p>
                  {errorMessage ||
                    'No pudimos obtener la información satelital del campo seleccionado.'}
                </p>
              </div>
              {onRetry && (
                <button
                  type="button"
                  className="telemetry-retry-btn"
                  onClick={onRetry}
                >
                  <RefreshCw size={13} />
                  <span>Reintentar</span>
                </button>
              )}
            </div>
          </section>
        )
      }

      const radicularPct = telemetria
        ? Math.round(telemetria.indice_humedad_radicular_pct)
        : null
      const superficialPct = telemetria
        ? Math.round(telemetria.indice_humedad_superficial_pct)
        : null
      const lluviaAnom =
        telemetria &&
          telemetria.anomalia_lluvia_90d_pct !== null &&
          telemetria.anomalia_lluvia_90d_pct !== undefined
          ? Math.round(telemetria.anomalia_lluvia_90d_pct)
          : null

      const moPct = getOrganicMatterPct(perfilSuelo)
      const moNormPct =
        moPct !== null ? Math.min(100, Math.round((moPct / 5.2) * 100)) : 0

      const soilPh =
        perfilSuelo && 'ph' in perfilSuelo && perfilSuelo.ph !== null
          ? perfilSuelo.ph
          : null
      const soilClay =
        perfilSuelo && 'arcilla_pct' in perfilSuelo ? perfilSuelo.arcilla_pct : null
      const soilSilt =
        perfilSuelo && 'limo_pct' in perfilSuelo ? perfilSuelo.limo_pct : null
      const soilSand =
        perfilSuelo && 'arena_pct' in perfilSuelo ? perfilSuelo.arena_pct : null
      const soilCarbon =
        perfilSuelo &&
        perfilSuelo.carbono_organico_g_kg !== null &&
        perfilSuelo.carbono_organico_g_kg !== undefined
          ? perfilSuelo.carbono_organico_g_kg
          : null

      const textureText = perfilSuelo?.textura_predominante
        ? formatSoilTexture(perfilSuelo.textura_predominante)
        : null

      const heatInfo =
        telemetria?.riesgo_termico_verano
          ? getHeatRiskMeaning(telemetria.riesgo_termico_verano)
          : null
      const humanDate = telemetria
        ? formatHumanDate(telemetria.fecha_ultimo_dato_valido)
        : null

      // Resumen ejecutivo en 1 oración (< 5 segundos)
      let quickSummarySentence = 'Se muestran los datos disponibles del lote.'
      if (radicularPct !== null) {
        if (radicularPct < 38) {
          const lluviaText =
            lluviaAnom === null
              ? 'con disponibilidad reciente medida por satélite'
              : lluviaAnom < 0
                ? `por debajo del promedio (${formatSignedAnomalyPct(lluviaAnom)})`
                : 'dentro del rango normal'
          quickSummarySentence = `El lote presenta una reserva hídrica ajustada (${radicularPct}%) y precipitaciones ${lluviaText}.`
        } else {
          quickSummarySentence = textureText
            ? `El lote registra buena disponibilidad hídrica en zona radicular (${radicularPct}%) sobre suelo ${textureText.toLowerCase()}.`
            : `El lote registra buena disponibilidad hídrica en zona radicular (${radicularPct}%).`
        }
      }

      const rotationConditionText = perfilSuelo?.condicion_rotacion_previa
        ? formatRotationCondition(perfilSuelo.condicion_rotacion_previa)
        : null
      const safeAdvertencias = humanizeAgronomicWarnings([advertencias])

      return (
        <section className="panel-section telemetry-section">
          {headerNode}

          {/* RESUMEN RÁPIDO EN 1 LÍNEA + FECHA HUMANA */}
          <div className="telemetry-summary-banner">
            <p className="telemetry-summary-text">{quickSummarySentence}</p>
            <div className="telemetry-meta-bar">
              <span>
                Último dato satelital:{' '}
                <strong>{humanDate ?? 'No disponible'}</strong>
              </span>
              {isWhatIfActive && (
                <span className="what-if-active-pill">Escenario simulado</span>
              )}
            </div>
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

          {/* GRILLA DE 2 TARJETAS: AGUA (AZUL) Y CALOR/SUELO (NARANJA) — MÁX 3 MÉTRICAS POR TARJETA */}
          <div className="telemetry-grid">
            {/* TARJETA 1: AGUA Y LLUVIAS */}
            <div className="telemetry-card water-card">
              <div className="telemetry-card-head">
                <span className="card-badge water">
                  <Droplets size={15} />
                  <span>Agua y lluvias</span>
                </span>
              </div>

              <div
                className="metric-block"
                title="Humedad guardada hasta 1 m de profundidad."
              >
                <div className="metric-label-row">
                  <span>Agua en las raíces</span>
                  {radicularPct !== null ? (
                    <strong className="metric-value water">
                      {radicularPct}% · {getRootWaterMeaning(radicularPct)}
                    </strong>
                  ) : (
                    <strong className="metric-value metric-unavailable">
                      No se puede mostrar en este momento
                    </strong>
                  )}
                </div>
                <div className="progress-track water-track">
                  <div
                    className="progress-fill water-fill"
                    style={{
                      width:
                        radicularPct !== null
                          ? `${Math.min(100, Math.max(4, radicularPct))}%`
                          : '0%',
                    }}
                  />
                </div>
              </div>

              <div
                className="metric-block"
                title="Humedad en los primeros 5 cm del suelo."
              >
                <div className="metric-label-row">
                  <span>Humedad para sembrar</span>
                  {superficialPct !== null ? (
                    <strong className="metric-value water">
                      {superficialPct}% · {getSurfaceWaterMeaning(superficialPct)}
                    </strong>
                  ) : (
                    <strong className="metric-value metric-unavailable">
                      No se puede mostrar en este momento
                    </strong>
                  )}
                </div>
                <div className="progress-track water-track">
                  <div
                    className="progress-fill water-fill-light"
                    style={{
                      width:
                        superficialPct !== null
                          ? `${Math.min(100, Math.max(4, superficialPct))}%`
                          : '0%',
                    }}
                  />
                </div>
              </div>

              <div
                className="rain-anomaly-box"
                title="Comparado con el promedio histórico de la zona (últimos 20 años)."
              >
                <div className="rain-anomaly-left">
                  <CloudRain size={16} />
                  <span>Lluvias de los últimos 3 meses</span>
                </div>
                {lluviaAnom !== null ? (
                  <strong
                    className={`rain-anomaly-val ${lluviaAnom < 0 ? 'deficit' : 'surplus'}`}
                  >
                    {formatSignedAnomalyPct(lluviaAnom)}
                  </strong>
                ) : (
                  <strong className="metric-value metric-unavailable">
                    No disponible
                  </strong>
                )}
              </div>
            </div>

            {/* TARJETA 2: CALOR Y SUELO */}
            <div className="telemetry-card heat-soil-card">
              <div className="telemetry-card-head">
                <span className="card-badge heat">
                  <Flame size={15} />
                  <span>Calor y salud del suelo</span>
                </span>
                {isRetryingFieldData && (
                  <span
                    className="telemetry-retrying-badge"
                    title="Actualizando datos reales de suelo y topografía"
                  >
                    <Loader2
                      size={14}
                      className="telemetry-retrying-spinner"
                      aria-label="Actualizando datos reales del lote"
                    />
                  </span>
                )}
              </div>

              <div
                className="metric-block"
                title="Días muy calurosos en el momento crítico del cultivo."
              >
                <div className="metric-label-row">
                  <span>Riesgo de golpe de calor</span>
                  {heatInfo ? (
                    <strong className="metric-value heat">{heatInfo.label}</strong>
                  ) : (
                    <strong className="metric-value metric-unavailable">
                      No se puede mostrar en este momento
                    </strong>
                  )}
                </div>
                <div className="progress-track heat-track">
                  <div
                    className="progress-fill heat-fill"
                    style={{ width: `${heatInfo ? heatInfo.percent : 0}%` }}
                  />
                </div>
              </div>

              <div
                className="metric-block"
                title="Indicador de fertilidad y salud del lote (calculado a partir del carbono orgánico del suelo)."
              >
                <div className="metric-label-row">
                  <span>Materia orgánica del suelo</span>
                  {moPct !== null ? (
                    <strong className="metric-value heat">
                      {moPct.toFixed(1)}% · {getOrganicMatterMeaning(moPct)}
                    </strong>
                  ) : (
                    <strong className="metric-value metric-unavailable">
                      No se puede mostrar en este momento
                    </strong>
                  )}
                </div>
                <div className="progress-track heat-track">
                  <div
                    className="progress-fill soil-fill"
                    style={{ width: `${moNormPct}%` }}
                  />
                </div>
              </div>

              <div
                className="soil-chip"
                title="Determina la capacidad de retención hídrica del suelo."
              >
                <Layers size={14} />
                <span>
                  Tipo de suelo:{' '}
                  <strong className={textureText ? '' : 'metric-unavailable'}>
                    {textureText ?? 'No se puede mostrar en este momento'}
                  </strong>
                </span>
              </div>
            </div>
          </div>

          {/* DIVULGACIÓN PROGRESIVA: VER DETALLE DEL SUELO Y RASTROJO */}
          <button
            type="button"
            className="detail-toggle-btn"
            onClick={() => setShowSoilDetail((prev) => !prev)}
            aria-expanded={showSoilDetail}
          >
            <span>
              {showSoilDetail
                ? 'Ocultar detalle del lote'
                : 'Ver detalle de cobertura y suelo'}
            </span>
            {showSoilDetail ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>

          {showSoilDetail && (
            <div className="winner-detail-drawer">
              <div className="soil-chip">
                <Sprout size={15} />
                <span>
                  <strong>Estado tras el último cultivo:</strong>{' '}
                  {latestCampaign
                    ? formatLatestCampaign(latestCampaign)
                    : (rotationConditionText ??
                      'Sin último cultivo registrado en este campo.')}
                  {latestCampaign && rotationConditionText
                    ? ` — ${rotationConditionText}`
                    : ''}
                </span>
              </div>

              {(soilPh !== null ||
                soilCarbon !== null ||
                (soilClay !== null && soilSilt !== null && soilSand !== null)) && (
                <div className="soil-chip">
                  <Layers size={15} />
                  <span>
                    <strong>Propiedades del suelo:</strong>{' '}
                    {[
                      soilPh !== null ? `pH ${soilPh.toFixed(1)}` : null,
                      soilCarbon !== null
                        ? `Carbono orgánico ${soilCarbon.toFixed(1)} g/kg`
                        : null,
                      soilClay !== null && soilSilt !== null && soilSand !== null
                        ? `Arcilla ${Math.round(soilClay)}% · Limo ${Math.round(soilSilt)}% · Arena ${Math.round(soilSand)}%`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </div>
              )}

              {topografia && (
                <div className="soil-chip">
                  <Mountain size={15} />
                  <span>
                    <strong>Topografía del terreno:</strong>{' '}
                    {Math.round(topografia.elevacion_m)} m s.n.m. · Pendiente{' '}
                    {topografia.pendiente_terreno_pct.toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
          )}
        </section>
      )
    }
