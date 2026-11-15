import { Info, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import type {
  CamposDistribucionPredictiva,
  DepartamentoReferencia,
  FaseEnso,
} from '../types/api'
import { formatQq } from '../utils/formatters'
import {
  DEFINICION_RINDE_BAJO,
  type Nivel,
  TEXTO_COBERTURA_SIN_RINDE,
  textoComparamosCon,
  textoDesvioNormal,
  textoReferenciaZona,
  textoRiesgoAnioMalo,
  textoRindeEsperado,
} from '../utils/lenguajeProductor'

interface RiesgoRindeResumenProps {
  datos: CamposDistribucionPredictiva
  nombreCultivo: string
  /** Cultivo de servicio (vicia, avena): no tiene rinde comercial. */
  esCobertura?: boolean
  /** Puntaje hidroclimático, solo para cuando no hay kg/ha. */
  hidroclimatico?: number | null
  aniosEvaluados?: number | null
  fase?: FaseEnso | null
  departamento?: DepartamentoReferencia | null
  /** Texto extra bajo el rango (FRONT-37: "El rango se achica a medida que avanza la campaña."). */
  notaRango?: string
}

function IconoNivel({ nivel }: { nivel: Nivel }) {
  if (nivel === 'malo') return <TrendingDown size={14} aria-hidden="true" />
  if (nivel === 'bueno') return <TrendingUp size={14} aria-hidden="true" />
  return <Minus size={14} aria-hidden="true" />
}

/** Barra año malo / año bueno con el esperado marcado y una línea en lo normal. */
function BarraRango({ malo, bueno, esperado, normal }: { malo: number; bueno: number; esperado: number; normal: number }) {
  const min = Math.min(malo, normal) * 0.9
  const max = Math.max(bueno, normal) * 1.05
  const pos = (v: number) => `${((v - min) / (max - min)) * 100}%`
  return (
    <div className="rr-rango">
      <div
        className="rr-rango-track"
        role="img"
        aria-label={`En un año malo cerca de ${formatQq(malo)}, en un año bueno cerca de ${formatQq(bueno)}; lo esperado es ${formatQq(esperado)} y lo normal ${formatQq(normal)}.`}
      >
        <div className="rr-rango-banda" style={{ left: pos(malo), width: `calc(${pos(bueno)} - ${pos(malo)})` }} />
        <div className="rr-rango-normal" style={{ left: pos(normal) }} title={`Normal en la zona: ${formatQq(normal)}`} />
        <div className="rr-rango-esperado" style={{ left: pos(esperado) }} title={`Esperado: ${formatQq(esperado)}`} />
      </div>
      <div className="rr-rango-etiquetas">
        <span>
          En un año malo: <strong>~{formatQq(malo)}</strong>
        </span>
        <span>
          En un año bueno: <strong>~{formatQq(bueno)}</strong>
        </span>
      </div>
    </div>
  )
}

/**
 * Bloque de FRONT-36: riesgo de año malo como frecuencia, rinde en qq/ha contra lo normal de la
 * zona y rango año malo / año bueno. Todos los textos salen de `utils/lenguajeProductor.ts`.
 */
export function RiesgoRindeResumen({
  datos,
  nombreCultivo,
  esCobertura = false,
  hidroclimatico,
  aniosEvaluados,
  fase,
  departamento,
  notaRango,
}: RiesgoRindeResumenProps) {
  const riesgo = textoRiesgoAnioMalo(datos, nombreCultivo)
  const rinde = datos.rinde_kg_ha
  const tieneRinde = rinde != null && rinde.esperado != null && rinde.normal != null
  const comparamos = textoComparamosCon(aniosEvaluados, fase)
  const referencia = tieneRinde ? textoReferenciaZona(departamento) : null

  return (
    <div className="rr-resumen">
      {riesgo && (
        <div className={`rr-fila rr-riesgo nivel-${riesgo.nivel}`}>
          <p className="rr-riesgo-linea">
            <strong className="rr-frecuencia">{riesgo.frecuencia}</strong> {riesgo.titulo}
            <span className="rr-info" title={DEFINICION_RINDE_BAJO} aria-label={DEFINICION_RINDE_BAJO}>
              <Info size={13} aria-hidden="true" />
            </span>
          </p>
          <p className="rr-detalle">
            <IconoNivel nivel={riesgo.nivel} />
            <span>{riesgo.detalle}</span>
          </p>
        </div>
      )}

      {tieneRinde && rinde ? (
        <div className="rr-fila">
          <p className="rr-rinde">
            Rinde esperado: <strong>{textoRindeEsperado(rinde.esperado as number, rinde.normal as number)}</strong>
          </p>
          {rinde.anio_malo != null && rinde.anio_bueno != null && (
            <BarraRango
              malo={rinde.anio_malo}
              bueno={rinde.anio_bueno}
              esperado={rinde.esperado as number}
              normal={rinde.normal as number}
            />
          )}
          {notaRango && <p className="rr-nota">{notaRango}</p>}
        </div>
      ) : (
        <div className="rr-fila">
          <p className="rr-rinde">
            {esCobertura
              ? TEXTO_COBERTURA_SIN_RINDE
              : (rinde?.motivo_sin_dato ??
                (hidroclimatico != null ? textoDesvioNormal(hidroclimatico).texto : null))}
          </p>
        </div>
      )}

      {(comparamos || referencia) && (
        <p className="rr-pie">
          {comparamos} {referencia}
        </p>
      )}
    </div>
  )
}
