import { useState } from 'react'
import { Sprout } from 'lucide-react'
import { CULTIVOS_CATALOGO } from '../data/demoFields'
import type { Campana, CultivoId } from '../types/api'

/** Cultivos con rinde MAGyP: los únicos con seguimiento (ML-18). */
const CULTIVOS_SEGUIBLES: CultivoId[] = [
  'trigo',
  'cebada',
  'maiz_temprano',
  'maiz_tardio',
  'soja_primera',
  'soja_segunda',
  'girasol',
  'sorgo',
]
const MAX_DIAS_ATRAS = 270

function isoLocal(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

interface RegistrarSiembraFormProps {
  /** Registra la campaña; la promesa rechaza con un mensaje para mostrar. */
  onRegistrar: (datos: { cultivo: CultivoId; campana: Campana; fechaSiembra: string }) => Promise<void>
}

/**
 * FRONT-37: "Registrar siembra". La campaña sale del cultivo; se ofrecen los 8 cultivos con rinde
 * (no solo los de la campaña vigente: en noviembre un trigo sembrado en junio está en su período crítico).
 */
export function RegistrarSiembraForm({ onRegistrar }: RegistrarSiembraFormProps) {
  // Fechas límite fijadas al montar (no en cada render).
  const [{ hoy, minimo }] = useState(() => {
    const ahora = new Date()
    const desde = new Date(ahora)
    desde.setDate(desde.getDate() - MAX_DIAS_ATRAS)
    return { hoy: ahora, minimo: desde }
  })

  const [abierto, setAbierto] = useState(false)
  const [cultivo, setCultivo] = useState<CultivoId | ''>('')
  const [fecha, setFecha] = useState<string>('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const porCampana = (campana: Campana) =>
    CULTIVOS_SEGUIBLES.filter((c) => CULTIVOS_CATALOGO[c]?.campana === campana)

  const fechaValida = fecha !== '' && fecha <= isoLocal(hoy) && fecha >= isoLocal(minimo)

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!cultivo || !fechaValida) return
    setEnviando(true)
    setError(null)
    try {
      await onRegistrar({ cultivo, campana: CULTIVOS_CATALOGO[cultivo].campana, fechaSiembra: fecha })
      setAbierto(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible registrar la siembra.')
    } finally {
      setEnviando(false)
    }
  }

  if (!abierto) {
    return (
      <section className="panel-section seguimiento-section">
        <p className="seg-invitacion">
          ¿Ya sembraste este lote? Registrá la siembra para seguir cómo viene la campaña semana a semana.
        </p>
        <button type="button" className="aviso-reintentar" onClick={() => setAbierto(true)}>
          <Sprout size={14} aria-hidden="true" />
          <span>Registrar siembra</span>
        </button>
      </section>
    )
  }

  return (
    <section className="panel-section seguimiento-section">
      <form className="seg-form" onSubmit={enviar}>
        <label>
          <span>Cultivo</span>
          <select value={cultivo} onChange={(e) => setCultivo(e.target.value as CultivoId)} required>
            <option value="" disabled>
              Elegí el cultivo
            </option>
            <optgroup label="Cultivos de verano">
              {porCampana('verano').map((c) => (
                <option key={c} value={c}>
                  {CULTIVOS_CATALOGO[c].nombre}
                </option>
              ))}
            </optgroup>
            <optgroup label="Cultivos de invierno">
              {porCampana('invierno').map((c) => (
                <option key={c} value={c}>
                  {CULTIVOS_CATALOGO[c].nombre}
                </option>
              ))}
            </optgroup>
          </select>
        </label>
        <label>
          <span>Fecha de siembra</span>
          <input
            type="date"
            value={fecha}
            min={isoLocal(minimo)}
            max={isoLocal(hoy)}
            onChange={(e) => setFecha(e.target.value)}
            required
          />
        </label>
        {fecha !== '' && !fechaValida && (
          <p className="seg-error">La fecha de siembra no puede ser futura ni de hace más de 9 meses.</p>
        )}
        {error && <p className="seg-error">{error}</p>}
        <div className="seg-form-acciones">
          <button type="button" className="detail-link-btn" onClick={() => setAbierto(false)}>
            Cancelar
          </button>
          <button type="submit" className="aviso-reintentar" disabled={!cultivo || !fechaValida || enviando}>
            <Sprout size={14} aria-hidden="true" />
            <span>{enviando ? 'Registrando…' : 'Registrar siembra'}</span>
          </button>
        </div>
      </form>
    </section>
  )
}
