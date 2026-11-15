import { useState } from 'react'
import { Trash2, Wheat } from 'lucide-react'
import { diaMes } from '../utils/lenguajeProductor'

export interface DatosCierre {
  fechaFin: string
  /** Rinde cosechado en kg/ha (se carga en qq/ha); null si no se informa. */
  rindeKgHa: number | null
  notas: string | null
}

interface AccionesCampanaProps {
  nombreCultivo: string
  /** Fecha de siembra (ISO): la cosecha no puede ser anterior. */
  fechaSiembra: string
  onCerrar: (datos: DatosCierre) => Promise<void>
  onBorrar: () => Promise<void>
}

function hoyIso(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * BACK-30 / FRONT-38: cerrar la campaña cuando se cosecha (fecha y, si se quiere, el rinde real)
 * o borrarla si se cargó por error. Cerrada, deja de aparecer como campaña en curso y pasa a
 * ser el "último cultivo" del lote.
 */
export function AccionesCampana({ nombreCultivo, fechaSiembra, onCerrar, onBorrar }: AccionesCampanaProps) {
  const [modo, setModo] = useState<'nada' | 'cerrar' | 'borrar'>('nada')
  const [hoy] = useState(hoyIso)
  const [fechaFin, setFechaFin] = useState<string>('')
  const [rindeQq, setRindeQq] = useState<string>('')
  const [notas, setNotas] = useState<string>('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const rindeNum = rindeQq.trim() === '' ? null : Number(rindeQq.replace(',', '.'))
  const rindeValido = rindeNum === null || (Number.isFinite(rindeNum) && rindeNum >= 0 && rindeNum <= 250)
  const fechaValida = fechaFin !== '' && fechaFin >= fechaSiembra && fechaFin <= hoy

  const ejecutar = async (accion: () => Promise<void>) => {
    setEnviando(true)
    setError(null)
    try {
      await accion()
      setModo('nada')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible guardar el cambio.')
    } finally {
      setEnviando(false)
    }
  }

  const cerrar = (e: React.FormEvent) => {
    e.preventDefault()
    if (!fechaValida || !rindeValido) return
    void ejecutar(() =>
      onCerrar({
        fechaFin,
        rindeKgHa: rindeNum === null ? null : Math.round(rindeNum * 100),
        notas: notas.trim() === '' ? null : notas.trim(),
      })
    )
  }

  if (modo === 'cerrar') {
    return (
      <form className="seg-form seg-acciones-form" onSubmit={cerrar}>
        <p className="seg-invitacion">
          <strong>Cerrar la campaña de {nombreCultivo}</strong>
        </p>
        <label>
          <span>Fecha de cosecha</span>
          <input
            type="date"
            value={fechaFin}
            min={fechaSiembra}
            max={hoy}
            onChange={(e) => setFechaFin(e.target.value)}
            required
          />
        </label>
        {fechaFin !== '' && !fechaValida && (
          <p className="seg-error">
            La cosecha tiene que ser entre la siembra ({diaMes(fechaSiembra)}) y hoy.
          </p>
        )}
        <label>
          <span>Rinde cosechado (qq/ha) — opcional</span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            max={250}
            step={0.5}
            value={rindeQq}
            onChange={(e) => setRindeQq(e.target.value)}
            placeholder="Ej.: 32"
          />
        </label>
        <p className="seg-ayuda">
          Con el rinde real de tu lote el sistema puede comparar lo que esperaba con lo que pasó y aprender de tu campo.
        </p>
        {!rindeValido && <p className="seg-error">El rinde tiene que ser un número entre 0 y 250 qq/ha.</p>}
        <label>
          <span>Notas — opcional</span>
          <textarea
            rows={2}
            maxLength={1000}
            value={notas}
            onChange={(e) => setNotas(e.target.value)}
            placeholder="Ej.: granizo en febrero, se resembró una parte"
          />
        </label>
        {error && <p className="seg-error">{error}</p>}
        <div className="seg-form-acciones">
          <button type="button" className="detail-link-btn" onClick={() => setModo('nada')} disabled={enviando}>
            Cancelar
          </button>
          <button type="submit" className="aviso-reintentar" disabled={!fechaValida || !rindeValido || enviando}>
            <Wheat size={14} aria-hidden="true" />
            <span>{enviando ? 'Guardando…' : 'Cerrar campaña'}</span>
          </button>
        </div>
      </form>
    )
  }

  if (modo === 'borrar') {
    return (
      <div className="seg-confirmar" role="alertdialog" aria-label="Confirmar borrado de la siembra">
        <p>
          ¿Borrar la siembra de <strong>{nombreCultivo}</strong> del {diaMes(fechaSiembra)}? Se borra también su
          seguimiento. No se puede deshacer.
        </p>
        {error && <p className="seg-error">{error}</p>}
        <div className="seg-form-acciones">
          <button type="button" className="detail-link-btn" onClick={() => setModo('nada')} disabled={enviando}>
            Cancelar
          </button>
          <button
            type="button"
            className="aviso-reintentar seg-boton-peligro"
            onClick={() => void ejecutar(onBorrar)}
            disabled={enviando}
          >
            <Trash2 size={14} aria-hidden="true" />
            <span>{enviando ? 'Borrando…' : 'Sí, borrar'}</span>
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="seg-acciones">
      <button type="button" className="aviso-reintentar" onClick={() => setModo('cerrar')}>
        <Wheat size={14} aria-hidden="true" />
        <span>Cerrar campaña (ya cosechada)</span>
      </button>
      <button type="button" className="detail-link-btn seg-link-peligro" onClick={() => setModo('borrar')}>
        <Trash2 size={13} aria-hidden="true" /> Borrar siembra
      </button>
    </div>
  )
}
