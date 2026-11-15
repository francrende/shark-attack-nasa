import { useCallback, useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Pencil,
  Pentagon,
  RotateCcw,
  Settings,
  Trash2,
  X,
} from 'lucide-react'
import type { UserField } from '../types/api'
import { getFieldColorByIndex } from '../theme/mapColors'
import { calculatePolygonAreaHa } from '../utils/geo'

interface FieldsSubheaderProps {
  fields: UserField[]
  selectedFieldId: string | null
  isLoading: boolean
  isSaving: boolean
  errorMsg: string | null
  isDrawing: boolean
  customPolygon: [number, number][]
  isDemo: boolean
  isUserSettingsOpen?: boolean
  onUserAction: () => void
  onSelectField: (field: UserField) => void
  onStartDrawing: () => void
  onCancelDrawing: () => void
  onUndoVertex: () => void
  onClearPolygon: () => void
  onSaveField: (nombre: string) => Promise<void>
}

export function FieldsSubheader({
  fields,
  selectedFieldId,
  isLoading,
  isSaving,
  errorMsg,
  isDrawing,
  customPolygon,
  isDemo,
  isUserSettingsOpen = false,
  onUserAction,
  onSelectField,
  onStartDrawing,
  onCancelDrawing,
  onUndoVertex,
  onClearPolygon,
  onSaveField,
}: FieldsSubheaderProps) {
  const [fieldName, setFieldName] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const pillsTrackRef = useRef<HTMLDivElement | null>(null)
  const measureRowRef = useRef<HTMLDivElement | null>(null)
  const [startIndex, setStartIndex] = useState(0)
  const [visibleCount, setVisibleCount] = useState<number>(fields.length)

  const recomputeVisiblePills = useCallback(() => {
    const track = pillsTrackRef.current
    const measureRow = measureRowRef.current
    if (!track || !measureRow || fields.length === 0) {
      setVisibleCount(fields.length)
      return
    }

    const availableWidth = track.clientWidth
    if (availableWidth <= 0) return

    const gap = 8
    const children = Array.from(measureRow.children) as HTMLElement[]
    const clampedStart = Math.min(startIndex, Math.max(0, fields.length - 1))
    if (clampedStart !== startIndex) {
      setStartIndex(clampedStart)
    }

    let usedWidth = 0
    let count = 0
    for (let i = clampedStart; i < children.length; i += 1) {
      const chipWidth = children[i].offsetWidth
      const nextWidth = count === 0 ? chipWidth : usedWidth + gap + chipWidth
      if (nextWidth <= availableWidth) {
        usedWidth = nextWidth
        count += 1
      } else {
        break
      }
    }

    setVisibleCount(Math.max(count, 0))
  }, [fields.length, startIndex])

  useLayoutEffect(() => {
    recomputeVisiblePills()
  }, [fields, isLoading, isDrawing, recomputeVisiblePills])

  useEffect(() => {
    const track = pillsTrackRef.current
    if (!track || typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', recomputeVisiblePills)
      return () => window.removeEventListener('resize', recomputeVisiblePills)
    }

    const observer = new ResizeObserver(() => {
      recomputeVisiblePills()
    })
    observer.observe(track)
    return () => observer.disconnect()
  }, [recomputeVisiblePills])

  const canScrollLeft = startIndex > 0
  const canScrollRight = startIndex + visibleCount < fields.length
  const visibleFields = fields.slice(startIndex, startIndex + visibleCount)

  const handleScrollFields = (direction: -1 | 1) => {
    if (direction === -1) {
      setStartIndex((prev) => Math.max(0, prev - 1))
      return
    }
    if (startIndex + visibleCount < fields.length) {
      setStartIndex((prev) => prev + 1)
    }
  }

  const drawnAreaHa = Math.round(calculatePolygonAreaHa(customPolygon))

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = fieldName.trim()
    if (!trimmed) {
      setLocalError('Ingrese un nombre para el campo.')
      return
    }
    if (customPolygon.length < 3) {
      setLocalError('Marque al menos 3 vértices en el mapa.')
      return
    }
    setLocalError(null)
    await onSaveField(trimmed)
    setFieldName('')
  }

  const handleCancel = () => {
    setFieldName('')
    setLocalError(null)
    onCancelDrawing()
  }

  if (isDrawing) {
    return (
      <div
        className="fields-subheader"
        role="region"
        aria-label="Delimitar nuevo campo"
      >
        <form className="fields-drawing-bar" onSubmit={handleSubmit}>
          <div className="fields-drawing-inputs">
            <Pentagon
              size={15}
              className="fields-drawing-icon"
              aria-hidden="true"
            />
            <input
              type="text"
              className="fields-name-input"
              placeholder="Nombre del nuevo campo (ej. Lote Norte)"
              value={fieldName}
              onChange={(e) => {
                setFieldName(e.target.value)
                if (localError) setLocalError(null)
              }}
              disabled={isSaving}
              aria-label="Nombre del nuevo campo"
            />
            <span className="fields-drawing-metrics">
              {customPolygon.length < 3
                ? `${customPolygon.length} / 3 vértices mínimos (clic en el mapa)`
                : `${customPolygon.length} vértices · ${drawnAreaHa} ha`}
            </span>
          </div>

          <div className="fields-drawing-actions">
            <button
              type="button"
              className="poly-action-btn"
              onClick={onUndoVertex}
              disabled={customPolygon.length === 0 || isSaving}
              title="Deshacer último vértice"
            >
              <RotateCcw size={14} aria-hidden="true" />
              <span>Deshacer</span>
            </button>
            <button
              type="button"
              className="poly-action-btn danger"
              onClick={onClearPolygon}
              disabled={customPolygon.length === 0 || isSaving}
              title="Limpiar vértices"
            >
              <Trash2 size={14} aria-hidden="true" />
              <span>Limpiar</span>
            </button>
            <button
              type="submit"
              className="poly-action-btn primary"
              disabled={
                customPolygon.length < 3 || !fieldName.trim() || isSaving
              }
            >
              <CheckCircle2 size={14} aria-hidden="true" />
              <span>{isSaving ? 'Guardando...' : 'Guardar campo'}</span>
            </button>
            <button
              type="button"
              className="poly-action-btn"
              onClick={handleCancel}
              disabled={isSaving}
              title="Cancelar delimitación"
            >
              <X size={14} aria-hidden="true" />
              <span>Cancelar</span>
            </button>
          </div>
        </form>

        {(localError || errorMsg) && (
          <div className="fields-subheader-error" role="alert">
            {localError || errorMsg}
          </div>
        )}
      </div>
    )
  }

  const userPillButton = (
    <button
      type="button"
      className={`fields-user-pill ${isUserSettingsOpen ? 'active' : ''}`}
      onClick={onUserAction}
      title={isDemo ? 'Iniciar sesión' : 'Ajustes de usuario'}
      aria-label={isDemo ? 'Iniciar sesión' : 'Ajustes de usuario'}
    >
      <Settings size={15} aria-hidden="true" />
    </button>
  )

  return (
    <div
      className="fields-floating-bar expanded"
      role="region"
      aria-label="Campos del usuario"
    >
      {userPillButton}

      <div className="fields-carousel-wrap">
        <button
          type="button"
          className="fields-scroll-btn"
          onClick={() => handleScrollFields(-1)}
          disabled={!canScrollLeft}
          aria-label="Desplazar campos hacia la izquierda"
          title="Campos anteriores"
        >
          <ChevronLeft size={15} aria-hidden="true" />
        </button>

        <div ref={pillsTrackRef} className="fields-pills-transparent">
          {isLoading ? (
            <span className="fields-status-pill">Cargando campos...</span>
          ) : fields.length === 0 ? (
            <span className="fields-status-pill">
              Sin campos registrados
            </span>
          ) : (
            visibleFields.map((field) => {
              const originalIdx = fields.findIndex((f) => f.id === field.id)
              const isSelected = field.id === selectedFieldId
              const { variant } = getFieldColorByIndex(originalIdx)
              return (
                <button
                  key={field.id}
                  type="button"
                  className={`field-chip-btn ${variant} ${isSelected ? 'selected' : ''}`}
                  onClick={() => onSelectField(field)}
                >
                  <span className="field-chip-dot" aria-hidden="true" />
                  <span className="field-chip-name">{field.nombre}</span>
                  {field.hectareas !== null && (
                    <span className="field-chip-ha">
                      {Math.round(field.hectareas)} ha
                    </span>
                  )}
                </button>
              )
            })
          )}

          {/* Fila oculta para medir el ancho exacto de cada pill y evitar cortes */}
          <div
            ref={measureRowRef}
            className="fields-measure-row"
            aria-hidden="true"
          >
            {fields.map((field, idx) => {
              const { variant } = getFieldColorByIndex(idx)
              return (
                <span key={field.id} className={`field-chip-btn ${variant}`}>
                  <span className="field-chip-dot" />
                  <span className="field-chip-name">{field.nombre}</span>
                  {field.hectareas !== null && (
                    <span className="field-chip-ha">
                      {Math.round(field.hectareas)} ha
                    </span>
                  )}
                </span>
              )
            })}
          </div>
        </div>

        <button
          type="button"
          className="fields-scroll-btn"
          onClick={() => handleScrollFields(1)}
          disabled={!canScrollRight}
          aria-label="Desplazar campos hacia la derecha"
          title="Siguientes campos"
        >
          <ChevronRight size={15} aria-hidden="true" />
        </button>
      </div>

      <button
        type="button"
        className="fields-new-icon-btn"
        onClick={onStartDrawing}
        aria-label="Nuevo campo"
        title="Nuevo campo"
      >
        <Pencil size={15} aria-hidden="true" />
      </button>

      {errorMsg && (
        <div className="fields-subheader-error" role="alert">
          {errorMsg}
        </div>
      )}
    </div>
  )
}
