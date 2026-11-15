import { AlertTriangle, CloudOff, Info, Loader2, RotateCw } from 'lucide-react'
import { estaDesactualizado } from '../services/ultimoResultado'
import { fechaHoraCorta, nombreFuente } from '../utils/lenguajeProductor'

/** Estados de la tabla "Estados cuando el backend no responde" de FRONT-36. */
export type EstadoDatos =
  | { tipo: 'despertando'; consultadoEn?: string | null }
  | { tipo: 'servicio_externo'; fuente: string | null }
  | { tipo: 'invalido'; mensaje: string }
  | { tipo: 'sin_conexion'; consultadoEn?: string | null }
  | { tipo: 'demo' }

interface AvisoEstadoDatosProps {
  estado: EstadoDatos
  onReintentar?: () => void
}

function textoGuardado(consultadoEn: string): string {
  const base = `Te mostramos el último resultado de este lote, del ${fechaHoraCorta(consultadoEn)}.`
  return estaDesactualizado(consultadoEn)
    ? `${base} Puede estar desactualizado: la humedad del suelo cambia de una semana a otra.`
    : base
}

export function AvisoEstadoDatos({ estado, onReintentar }: AvisoEstadoDatosProps) {
  let icono = <Info size={16} aria-hidden="true" />
  let titulo = ''
  let detalle: string | null = null
  let reintentar = false
  let clase = 'aviso-datos'

  switch (estado.tipo) {
    case 'despertando':
      icono = <Loader2 size={16} className="aviso-girando" aria-hidden="true" />
      titulo = 'Despertando el servidor, puede tardar hasta un minuto…'
      detalle = estado.consultadoEn ? textoGuardado(estado.consultadoEn) : null
      clase += ' aviso-info'
      break
    case 'servicio_externo':
      icono = <AlertTriangle size={16} aria-hidden="true" />
      titulo = `No pudimos consultar ${nombreFuente(estado.fuente)} en este momento.`
      detalle = 'Probá de nuevo en unos minutos.'
      reintentar = true
      clase += ' aviso-alerta'
      break
    case 'invalido':
      icono = <AlertTriangle size={16} aria-hidden="true" />
      titulo = estado.mensaje
      clase += ' aviso-alerta'
      break
    case 'sin_conexion':
      icono = <CloudOff size={16} aria-hidden="true" />
      if (estado.consultadoEn) {
        titulo = 'Sin conexión con el servidor.'
        detalle = textoGuardado(estado.consultadoEn)
      } else {
        titulo = 'No pudimos conectarnos con el servidor.'
        detalle = 'Revisá tu conexión o probá de nuevo en unos minutos.'
      }
      reintentar = true
      clase += ' aviso-alerta'
      break
    case 'demo':
      titulo = 'Modo demostración: datos de ejemplo, no corresponden a tu lote.'
      clase += ' aviso-demo'
      break
  }

  return (
    <div className={clase} role={estado.tipo === 'despertando' ? 'status' : 'alert'}>
      <span className="aviso-icono">{icono}</span>
      <div className="aviso-texto">
        <strong>{titulo}</strong>
        {detalle && <p>{detalle}</p>}
      </div>
      {reintentar && onReintentar && (
        <button type="button" className="aviso-reintentar" onClick={onReintentar}>
          <RotateCw size={14} aria-hidden="true" />
          <span>Reintentar</span>
        </button>
      )}
    </div>
  )
}
