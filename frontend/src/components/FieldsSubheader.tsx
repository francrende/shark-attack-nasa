import { useState, type FormEvent } from 'react'
import {
  CheckCircle2,
  MapPin,
  Pencil,
  Pentagon,
  RotateCcw,
  Trash2,
  X,
} from 'lucide-react'
import type { UserField } from '../types/api'
import { calculatePolygonAreaHa } from '../utils/geo'

const PILL_COLOR_VARIANTS = [
  'variant-olive',
  'variant-terracotta',
  'variant-water',
  'variant-earth',
  'variant-gold',
] as const

interface FieldsSubheaderProps {
  fields: UserField[]
  selectedFieldId: string | null
  isLoading: boolean
  isSaving: boolean
  errorMsg: string | null
  isOpen: boolean
  isDrawing: boolean
  customPolygon: [number, number][]
  onToggleOpen: () => void
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
  isOpen,
  isDrawing,
  customPolygon,
  onToggleOpen,
  onSelectField,
  onStartDrawing,
  onCancelDrawing,
  onUndoVertex,
  onClearPolygon,
  onSaveField,
}: FieldsSubheaderProps) {
  const [fieldName, setFieldName] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

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

  if (!isOpen) {
    return (
      <div className="fields-floating-bar">
        <button
          type="button"
          className="fields-toggle-pill"
          onClick={onToggleOpen}
          aria-expanded="false"
        >
          <MapPin size={14} aria-hidden="true" />
          <span>Mis campos ({fields.length})</span>
        </button>
        <button
          type="button"
          className="fields-new-btn"
          onClick={onStartDrawing}
        >
          <Pencil size={14} aria-hidden="true" />
          <span>Nuevo campo</span>
        </button>
      </div>
    )
  }

  return (
    <div
      className="fields-floating-bar expanded"
      role="region"
      aria-label="Mis campos"
    >
      <button
        type="button"
        className="fields-close-btn"
        onClick={onToggleOpen}
        aria-expanded="true"
        aria-label="Cerrar lista de campos"
        title="Cerrar lista de campos"
      >
        <X size={15} aria-hidden="true" />
      </button>

      <div className="fields-pills-transparent">
        {isLoading ? (
          <span className="fields-status-pill">Cargando campos...</span>
        ) : fields.length === 0 ? (
          <span className="fields-status-pill">
            Sin campos registrados
          </span>
        ) : (
          fields.map((field, idx) => {
            const isSelected = field.id === selectedFieldId
            const variant =
              PILL_COLOR_VARIANTS[idx % PILL_COLOR_VARIANTS.length]
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
