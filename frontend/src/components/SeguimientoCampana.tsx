import { type ReactNode, useState } from 'react'
import { CalendarCheck, Info } from 'lucide-react'
import type { PuntoSeguimiento, SeguimientoResponse } from '../types/api'
import { formatQq, kgHaAQq } from '../utils/formatters'
import {
  TEXTO_LO_QUE_NO_VE,
  diaMes,
  frecuencia,
  textoEncabezadoSiembra,
  textoEtapa,
  textoEvolucion,
  textoPorQue,
  textoUltimoDato,
} from '../utils/lenguajeProductor'
import { AvisoEstadoDatos, type EstadoDatos } from './AvisoEstadoDatos'
import { RiesgoRindeResumen } from './RiesgoRindeResumen'

interface SeguimientoCampanaProps {
  nombreCultivo: string
  seguimiento: SeguimientoResponse | null
  cargando: boolean
  aviso: EstadoDatos | null
  onReintentar: () => void
  /** FRONT-38: cerrar o borrar la campaña (se muestra siempre, aunque el seguimiento falle). */
  acciones?: ReactNode
}

const ANCHO = 320
const ALTO_PANEL = 90
const MARGEN = { izq: 34, der: 8, arriba: 10, abajo: 18 }

function dias(iso: string): number {
  return Date.parse(`${iso}T00:00:00Z`) / 86_400_000
}

/** Gráfico semanal: arriba "cuántas de cada 10", abajo año malo / año bueno en qq/ha. */
function GraficoSemanal({ s }: { s: SeguimientoResponse }) {
  const x0 = dias(s.fecha_siembra)
  const x1 = Math.max(dias(s.fin_periodo_critico), x0 + 1)
  const ancho = ANCHO - MARGEN.izq - MARGEN.der
  const x = (iso: string) => MARGEN.izq + ((dias(iso) - x0) / (x1 - x0)) * ancho
  const conProb = s.serie.filter((p) => p.prob_anio_malo != null)
  const conRinde = s.serie.filter((p) => p.rinde_kg_ha?.anio_malo != null && p.rinde_kg_ha?.anio_bueno != null)

  const panelProb = conProb.length > 0
  const alto = (panelProb ? ALTO_PANEL : 0) + (conRinde.length > 0 ? ALTO_PANEL : 0) + MARGEN.abajo + MARGEN.arriba
  const yProb = (p: number) => MARGEN.arriba + (1 - Math.min(p, 0.5) / 0.5) * (ALTO_PANEL - 12)

  const qqs = conRinde.flatMap((p) => [p.rinde_kg_ha!.anio_malo!, p.rinde_kg_ha!.anio_bueno!])
  if (s.rinde_normal_kg_ha != null) qqs.push(s.rinde_normal_kg_ha)
  const qMin = Math.min(...qqs) * 0.9
  const qMax = Math.max(...qqs) * 1.05
  const base2 = MARGEN.arriba + (panelProb ? ALTO_PANEL : 0)
  const yQq = (kg: number) => base2 + (1 - (kg - qMin) / Math.max(qMax - qMin, 1)) * (ALTO_PANEL - 12)

  const linea = (pts: PuntoSeguimiento[], y: (p: PuntoSeguimiento) => number) =>
    pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.fecha).toFixed(1)},${y(p).toFixed(1)}`).join(' ')

  return (
    <svg
      className="seg-grafico"
      viewBox={`0 0 ${ANCHO} ${alto}`}
      role="img"
      aria-label="Evolución semanal del riesgo de año malo y del rinde esperado desde la siembra"
    >
      {/* Período que define el rinde */}
      <rect
        className="seg-periodo"
        x={x(s.inicio_periodo_critico)}
        y={MARGEN.arriba - 4}
        width={Math.max(0, x(s.fin_periodo_critico) - x(s.inicio_periodo_critico))}
        height={alto - MARGEN.abajo - MARGEN.arriba + 4}
      />

      {panelProb && (
        <g>
          <text className="seg-eje" x={2} y={yProb(0.5) + 4}>1 de 2</text>
          <text className="seg-eje" x={2} y={yProb(0) + 4}>0</text>
          {s.prob_anio_malo_tipica != null && (
            <line
              className="seg-habitual"
              x1={MARGEN.izq}
              x2={ANCHO - MARGEN.der}
              y1={yProb(s.prob_anio_malo_tipica)}
              y2={yProb(s.prob_anio_malo_tipica)}
            >
              <title>{`Lo habitual: ${frecuencia(s.prob_anio_malo_tipica)}`}</title>
            </line>
          )}
          <path className="seg-linea-prob" d={linea(conProb, (p) => yProb(p.prob_anio_malo!))} />
          {conProb.map((p) => (
            <circle key={p.fecha} className="seg-punto-prob" cx={x(p.fecha)} cy={yProb(p.prob_anio_malo!)} r={3}>
              <title>{`${p.dias_observados === 0 ? 'Al sembrar' : `Semana del ${diaMes(p.fecha)}`}: ${frecuencia(p.prob_anio_malo!)} con rinde bajo`}</title>
            </circle>
          ))}
        </g>
      )}

      {conRinde.length > 0 && (
        <g>
          <text className="seg-eje" x={2} y={yQq(qMax) + 8}>{Math.round(kgHaAQq(qMax))}</text>
          <text className="seg-eje" x={2} y={yQq(qMin)}>{Math.round(kgHaAQq(qMin))}</text>
          <path
            className="seg-banda"
            d={`${linea(conRinde, (p) => yQq(p.rinde_kg_ha!.anio_bueno!))} ${[...conRinde]
              .reverse()
              .map((p) => `L${x(p.fecha).toFixed(1)},${yQq(p.rinde_kg_ha!.anio_malo!).toFixed(1)}`)
              .join(' ')} Z`}
          />
          {s.rinde_normal_kg_ha != null && (
            <line
              className="seg-habitual"
              x1={MARGEN.izq}
              x2={ANCHO - MARGEN.der}
              y1={yQq(s.rinde_normal_kg_ha)}
              y2={yQq(s.rinde_normal_kg_ha)}
            >
              <title>{`Normal en la zona: ${formatQq(s.rinde_normal_kg_ha)}`}</title>
            </line>
          )}
          <path
            className="seg-linea-rinde"
            d={linea(conRinde, (p) => yQq(p.rinde_kg_ha!.esperado ?? p.rinde_kg_ha!.normal ?? 0))}
          />
          {conRinde.map((p) => (
            <circle
              key={p.fecha}
              className="seg-punto-rinde"
              cx={x(p.fecha)}
              cy={yQq(p.rinde_kg_ha!.esperado ?? 0)}
              r={3}
            >
              <title>{`${p.dias_observados === 0 ? 'Al sembrar' : `Semana del ${diaMes(p.fecha)}`}: ${formatQq(p.rinde_kg_ha!.esperado ?? 0)} (año malo ~${formatQq(p.rinde_kg_ha!.anio_malo!)}, año bueno ~${formatQq(p.rinde_kg_ha!.anio_bueno!)})`}</title>
            </circle>
          ))}
        </g>
      )}

      <text className="seg-eje" x={x(s.fecha_siembra)} y={alto - 4}>{diaMes(s.fecha_siembra)}</text>
      <text className="seg-eje" x={x(s.inicio_periodo_critico)} y={alto - 4}>{diaMes(s.inicio_periodo_critico)}</text>
      <text className="seg-eje seg-eje-fin" x={x(s.fin_periodo_critico)} y={alto - 4} textAnchor="end">
        {diaMes(s.fin_periodo_critico)}
      </text>
    </svg>
  )
}

function TablaTecnica({ s }: { s: SeguimientoResponse }) {
  return (
    <table className="detalle-tecnico-tabla">
      <thead>
        <tr>
          <th scope="col">Fecha</th>
          <th scope="col">Días obs.</th>
          <th scope="col">Prob.</th>
          <th scope="col">Esperado</th>
          <th scope="col">Malo / bueno</th>
        </tr>
      </thead>
      <tbody>
        {s.serie.map((p) => (
          <tr key={p.fecha}>
            <td>{diaMes(p.fecha)}</td>
            <td>{p.dias_observados}</td>
            <td>{p.prob_anio_malo == null ? '—' : `${Math.round(p.prob_anio_malo * 100)}%`}</td>
            <td>{p.rinde_kg_ha?.esperado == null ? '—' : `${p.rinde_kg_ha.esperado} kg/ha`}</td>
            <td>
              {p.rinde_kg_ha?.anio_malo == null
                ? '—'
                : `${p.rinde_kg_ha.anio_malo} / ${p.rinde_kg_ha.anio_bueno} kg/ha`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** FRONT-37: cómo viene la campaña ya sembrada, en lenguaje de productor. */
export function SeguimientoCampana({
  nombreCultivo,
  seguimiento,
  cargando,
  aviso,
  onReintentar,
  acciones,
}: SeguimientoCampanaProps) {
  const [tecnico, setTecnico] = useState(false)

  return (
    <section className="panel-section seguimiento-section" aria-live="polite" aria-busy={cargando}>
      <div className="section-header-row">
        <h2 className="section-title">
          <CalendarCheck size={16} aria-hidden="true" /> Cómo viene la campaña
        </h2>
      </div>

      {aviso && <AvisoEstadoDatos estado={aviso} onReintentar={onReintentar} />}
      {cargando && !seguimiento && <p className="seg-cargando">Consultando datos satelitales…</p>}

      {seguimiento && (
        <SeguimientoContenido
          s={seguimiento}
          nombreCultivo={nombreCultivo}
          tecnico={tecnico}
          onTecnico={() => setTecnico((v) => !v)}
        />
      )}

      {acciones}
    </section>
  )
}

function SeguimientoContenido({
  s,
  nombreCultivo,
  tecnico,
  onTecnico,
}: {
  s: SeguimientoResponse
  nombreCultivo: string
  tecnico: boolean
  onTecnico: () => void
}) {
  const primero = s.serie[0]
  const ultimo = s.serie[s.serie.length - 1]
  const evolucion = textoEvolucion(primero?.prob_anio_malo ?? null, ultimo?.prob_anio_malo ?? null, s.prob_anio_malo_tipica)
  const avancePct = Math.round((s.dias_observados / s.dias_periodo_critico) * 100)

  return (
    <div className="seg-contenido">
      <p className="seg-encabezado">
        <strong>{textoEncabezadoSiembra(nombreCultivo, s.fecha_siembra)}</strong>
      </p>
      <p className="seg-etapa">{textoEtapa(s)}</p>
      {s.etapa === 'en_curso' && (
        <div
          className="seg-avance"
          role="progressbar"
          aria-valuenow={avancePct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Avance del período que define el rinde"
        >
          <div className="seg-avance-relleno" style={{ width: `${avancePct}%` }} />
        </div>
      )}

      {evolucion && s.serie.length > 1 && (
        <p className={`seg-evolucion nivel-${evolucion.nivel}`}>
          Riesgo de año malo: <strong>{evolucion.texto}</strong>{' '}
          {evolucion.cambio && (
            <span className="seg-flecha">
              {evolucion.flecha} {evolucion.cambio}
            </span>
          )}
        </p>
      )}

      {s.observado && <p className="seg-porque">{textoPorQue(s.observado)}</p>}

      {ultimo && (
        <RiesgoRindeResumen
          datos={{
            prob_anio_malo: ultimo.prob_anio_malo,
            prob_anio_malo_tipica: s.prob_anio_malo_tipica,
            anticipa_diferencias: ultimo.prob_anio_malo != null,
            rinde_kg_ha: ultimo.rinde_kg_ha,
          }}
          nombreCultivo={nombreCultivo}
          departamento={s.departamento_referencia}
          notaRango={s.rango_por_avance ? 'El rango se achica a medida que avanza la campaña.' : undefined}
        />
      )}

      {s.serie.length > 1 && <GraficoSemanal s={s} />}

      <p className="rr-pie">
        <Info size={12} aria-hidden="true" /> {textoUltimoDato(s.fecha_ultimo_dato)} {TEXTO_LO_QUE_NO_VE}
      </p>

      <button type="button" className="detail-link-btn detalle-tecnico-btn" onClick={onTecnico} aria-expanded={tecnico}>
        {tecnico ? '− Ocultar detalle técnico' : 'Ver detalle técnico'}
      </button>
      {tecnico && <TablaTecnica s={s} />}
    </div>
  )
}
