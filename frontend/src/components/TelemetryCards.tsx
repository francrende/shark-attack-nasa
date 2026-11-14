import { useState } from 'react'
import {
  ChevronDown,
  ChevronUp,
  CloudRain,
  Droplets,
  Flame,
  Layers,
  MapPin,
  Sprout,
} from 'lucide-react'
import type { Coordenadas, PerfilSuelo, TelemetriaNasa } from '../types/api'
import {
  formatHumanDate,
  formatSignedAnomalyPct,
} from '../utils/formatters'

interface TelemetryCardsProps {
  ubicacion: Coordenadas
  loteLabel: string
  superficieHa: number | null
  telemetria: TelemetriaNasa
  perfilSuelo: PerfilSuelo
  isWhatIfActive: boolean
}

function formatSoilTexture(textureRaw: string): string {
  const clean = textureRaw.replace(/_/g, ' ')
  return clean.charAt(0).toUpperCase() + clean.slice(1)
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
  if (lower === 'extremo') return { label: 'Riesgo muy alto', percent: 92 }
  if (lower === 'alto') return { label: 'Riesgo alto', percent: 76 }
  if (lower === 'moderado') return { label: 'Riesgo medio', percent: 48 }
  return { label: 'Riesgo bajo', percent: 24 }
}

function getOrganicMatterMeaning(socGKg: number): string {
  if (socGKg < 17) return 'Baja fertilidad'
  if (socGKg < 20.5) return 'Nivel medio'
  return 'Suelo bien nutrido'
}

export function TelemetryCards({
  ubicacion,
  loteLabel,
  superficieHa,
  telemetria,
  perfilSuelo,
  isWhatIfActive,
}: TelemetryCardsProps) {
  const [showSoilDetail, setShowSoilDetail] = useState<boolean>(false)

  const radicularPct = Math.round(telemetria.indice_humedad_radicular_pct)
  const superficialPct = Math.round(telemetria.indice_humedad_superficial_pct)
  const lluviaAnom = Math.round(telemetria.anomalia_lluvia_90d_pct)
  const socRounded = Math.round(perfilSuelo.carbono_organico_g_kg)
  const socNormPct = Math.min(100, Math.round((socRounded / 30) * 100))

  const heatInfo = getHeatRiskMeaning(telemetria.riesgo_termico_verano)
  const humanDate = formatHumanDate(telemetria.fecha_ultimo_dato_valido)

  // Resumen en 1 oración para responder "¿Cómo está mi lote hoy?" en < 5 segundos
  const quickSummarySentence =
    radicularPct < 38
      ? `Hoy tu lote tiene una reserva de agua ajustada (${radicularPct}%) y lluvias ${lluviaAnom < 0 ? `por debajo de lo normal (${formatSignedAnomalyPct(lluviaAnom)})` : 'normales'}.`
      : `Hoy tu lote cuenta con buena humedad en las raíces (${radicularPct}%) y suelo ${formatSoilTexture(perfilSuelo.textura_predominante).toLowerCase()}.`

  return (
    <section className="panel-section telemetry-section">
      <div className="section-header-row">
        <div>
          <span className="section-eyebrow">ESTADO ACTUAL DEL LOTE</span>
          <h2 className="section-title">¿Cómo está mi lote hoy?</h2>
          <p className="telemetry-lote-subtitle">{loteLabel}</p>
        </div>
        <div
          className="coords-pill"
          title="Ubicación del lote (centroide analizado)"
        >
          <MapPin size={13} />
          <span>Ubicación del lote:</span>
          <code>
            {ubicacion.lat.toFixed(3)}, {ubicacion.lon.toFixed(3)}
          </code>
          {superficieHa !== null && superficieHa > 0 && (
            <span className="coords-ha">{Math.round(superficieHa)} ha</span>
          )}
        </div>
      </div>

      {/* RESUMEN RÁPIDO EN 1 LÍNEA + FECHA HUMANA */}
      <div className="telemetry-summary-banner">
        <p className="telemetry-summary-text">{quickSummarySentence}</p>
        <div className="telemetry-meta-bar">
          <span>
            Último dato satelital: <strong>{humanDate}</strong>
          </span>
          {isWhatIfActive && (
            <span className="what-if-active-pill">Escenario simulado</span>
          )}
        </div>
      </div>

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
              <strong className="metric-value water">
                {radicularPct}% · {getRootWaterMeaning(radicularPct)}
              </strong>
            </div>
            <div className="progress-track water-track">
              <div
                className="progress-fill water-fill"
                style={{ width: `${Math.min(100, Math.max(4, radicularPct))}%` }}
              />
            </div>
          </div>

          <div
            className="metric-block"
            title="Humedad en los primeros 5 cm del suelo."
          >
            <div className="metric-label-row">
              <span>Humedad para sembrar</span>
              <strong className="metric-value water">
                {superficialPct}% · {getSurfaceWaterMeaning(superficialPct)}
              </strong>
            </div>
            <div className="progress-track water-track">
              <div
                className="progress-fill water-fill-light"
                style={{
                  width: `${Math.min(100, Math.max(4, superficialPct))}%`,
                }}
              />
            </div>
          </div>

          <div
            className="rain-anomaly-box"
            title="Comparado con lo normal en tu zona (últimos 20 años)."
          >
            <div className="rain-anomaly-left">
              <CloudRain size={16} />
              <span>Lluvias de los últimos 3 meses</span>
            </div>
            <strong
              className={`rain-anomaly-val ${lluviaAnom < 0 ? 'deficit' : 'surplus'}`}
            >
              {formatSignedAnomalyPct(lluviaAnom)}
            </strong>
          </div>
        </div>

        {/* TARJETA 2: CALOR Y SUELO */}
        <div className="telemetry-card heat-soil-card">
          <div className="telemetry-card-head">
            <span className="card-badge heat">
              <Flame size={15} />
              <span>Calor y salud del suelo</span>
            </span>
          </div>

          <div
            className="metric-block"
            title="Días muy calurosos en el momento crítico del cultivo."
          >
            <div className="metric-label-row">
              <span>Riesgo de golpe de calor</span>
              <strong className="metric-value heat">{heatInfo.label}</strong>
            </div>
            <div className="progress-track heat-track">
              <div
                className="progress-fill heat-fill"
                style={{ width: `${heatInfo.percent}%` }}
              />
            </div>
          </div>

          <div
            className="metric-block"
            title="Indicador de fertilidad y salud del lote."
          >
            <div className="metric-label-row">
              <span>Materia orgánica del suelo</span>
              <strong className="metric-value heat">
                {socRounded} g/kg · {getOrganicMatterMeaning(socRounded)}
              </strong>
            </div>
            <div className="progress-track heat-track">
              <div
                className="progress-fill soil-fill"
                style={{ width: `${socNormPct}%` }}
              />
            </div>
          </div>

          <div
            className="soil-chip"
            title="Define cuánta agua retiene tu suelo."
          >
            <Layers size={14} />
            <span>
              Tipo de suelo:{' '}
              <strong>
                {formatSoilTexture(perfilSuelo.textura_predominante)}
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
              {formatRotationCondition(perfilSuelo.condicion_rotacion_previa)}
            </span>
          </div>
        </div>
      )}
    </section>
  )
}
