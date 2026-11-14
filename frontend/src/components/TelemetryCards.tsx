import {
  CloudRain,
  Droplets,
  Flame,
  Layers,
  Satellite,
  Sprout,
} from 'lucide-react'
import type { Coordenadas, PerfilSuelo, TelemetriaNasa } from '../types/api'

interface TelemetryCardsProps {
  ubicacion: Coordenadas
  loteLabel: string
  superficieHa: number | null
  telemetria: TelemetriaNasa
  perfilSuelo: PerfilSuelo
  isWhatIfActive: boolean
}

function formatSoilTexture(textureRaw: string): string {
  return textureRaw
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase())
}

function formatRotationCondition(condRaw: string): string {
  const map: Record<string, string> = {
    deficit_rastrojo_por_soja: 'Déficit de rastrojo tras Soja (baja relación C/N)',
    buena_cobertura_graminea: 'Buena cobertura de rastrojo gramíneo',
    suelo_enriquecido_en_nitrogeno: 'Suelo enriquecido en N por leguminosa de servicio',
    alerta_extraccion_nutrientes: 'Alerta de extracción y baja cobertura superficial',
    rotacion_equilibrada_oleaginosa: 'Rotación equilibrada post-oleaginosa',
  }
  return map[condRaw] ?? condRaw.replace(/_/g, ' ')
}

export function TelemetryCards({
  ubicacion,
  loteLabel,
  superficieHa,
  telemetria,
  perfilSuelo,
  isWhatIfActive,
}: TelemetryCardsProps) {
  const radicularPct = telemetria.indice_humedad_radicular_pct
  const superficialPct = telemetria.indice_humedad_superficial_pct
  const lluviaAnom = telemetria.anomalia_lluvia_90d_pct
  const socNormPct = Math.min(
    100,
    Math.round((perfilSuelo.carbono_organico_g_kg / 30) * 100)
  )

  const riesgoTermicoLower = telemetria.riesgo_termico_verano.toLowerCase()
  const heatRiskPercent =
    riesgoTermicoLower === 'extremo'
      ? 92
      : riesgoTermicoLower === 'alto'
        ? 76
        : riesgoTermicoLower === 'moderado'
          ? 48
          : 24

  return (
    <section className="panel-section telemetry-section">
      <div className="section-header-row">
        <div>
          <span className="section-eyebrow">
            <Satellite size={13} />
            <span>PASO 1 · TELEMETRÍA SATELITAL Y SUELO</span>
          </span>
          <h2 className="section-title">{loteLabel}</h2>
        </div>
        <div className="coords-pill">
          <code>
            {ubicacion.lat.toFixed(4)}, {ubicacion.lon.toFixed(4)}
          </code>
          {superficieHa !== null && superficieHa > 0 && (
            <span className="coords-ha">{superficieHa} ha</span>
          )}
        </div>
      </div>

      <div className="telemetry-meta-bar">
        <span>
          Última lectura satelital consolidada:{' '}
          <strong>{telemetria.fecha_ultimo_dato_valido}</strong>
        </span>
        {isWhatIfActive && (
          <span className="what-if-active-pill">Escenario Simulado Activo</span>
        )}
      </div>

      {/* GRILLA DE 2 DIMENSIONES: HIDROLOGÍA (#4A7B9D) Y CALOR/SUELO (#F05D23) */}
      <div className="telemetry-grid">
        {/* TARJETA 1: HIDROLOGÍA SATELITAL NASA (AZUL #4A7B9D) */}
        <div className="telemetry-card water-card">
          <div className="telemetry-card-head">
            <span className="card-badge water">
              <Droplets size={14} />
              <span>Agua en el Suelo y Lluvias</span>
            </span>
            <span className="sensor-tag">Satélite NASA</span>
          </div>

          <div className="metric-block">
            <div className="metric-label-row">
              <span>Agua en Zona de Raíces (hasta 1 m)</span>
              <strong className="metric-value water">{radicularPct}%</strong>
            </div>
            <div className="progress-track water-track">
              <div
                className="progress-fill water-fill"
                style={{ width: `${Math.min(100, Math.max(4, radicularPct))}%` }}
              />
            </div>
            <span className="metric-subtext">
              {radicularPct < 38
                ? 'Reserva ajustada: poca agua guardada en profundidad'
                : radicularPct < 55
                  ? 'Reserva intermedia disponible para las raíces'
                  : 'Muy buena reserva de agua acumulada en el perfil'}
            </span>
          </div>

          <div className="metric-block">
            <div className="metric-label-row">
              <span>Humedad Superficial para Siembra (0–5 cm)</span>
              <strong className="metric-value water">{superficialPct}%</strong>
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

          <div className="rain-anomaly-box">
            <div className="rain-anomaly-left">
              <CloudRain size={16} />
              <span>Lluvias últimos 3 meses vs. promedio</span>
            </div>
            <strong
              className={`rain-anomaly-val ${lluviaAnom < 0 ? 'deficit' : 'surplus'}`}
            >
              {lluviaAnom > 0 ? `+${lluviaAnom}%` : `${lluviaAnom}%`}
            </strong>
          </div>
        </div>

        {/* TARJETA 2: CALOR Y SALUD DEL SUELO (NARANJA TERRACOTA #F05D23) */}
        <div className="telemetry-card heat-soil-card">
          <div className="telemetry-card-head">
            <span className="card-badge heat">
              <Flame size={14} />
              <span>Calor y Salud del Suelo</span>
            </span>
            <span className="sensor-tag">Suelo & Clima</span>
          </div>

          <div className="metric-block">
            <div className="metric-label-row">
              <span>Riesgo de Golpes de Calor en Verano</span>
              <strong className="metric-value heat">
                {telemetria.riesgo_termico_verano.toUpperCase()}
              </strong>
            </div>
            <div className="progress-track heat-track">
              <div
                className="progress-fill heat-fill"
                style={{ width: `${heatRiskPercent}%` }}
              />
            </div>
          </div>

          <div className="metric-block">
            <div className="metric-label-row">
              <span>Materia Orgánica / Carbono del Suelo</span>
              <strong className="metric-value heat">
                {perfilSuelo.carbono_organico_g_kg} g/kg
              </strong>
            </div>
            <div className="progress-track heat-track">
              <div
                className="progress-fill soil-fill"
                style={{ width: `${socNormPct}%` }}
              />
            </div>
          </div>

          <div className="soil-details-footer">
            <div className="soil-chip">
              <Layers size={13} />
              <span>
                Textura: <strong>{formatSoilTexture(perfilSuelo.textura_predominante)}</strong>
              </span>
            </div>
            <div className="soil-chip">
              <Sprout size={13} />
              <span>{formatRotationCondition(perfilSuelo.condicion_rotacion_previa)}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
