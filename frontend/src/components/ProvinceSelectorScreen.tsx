import { useState } from 'react'
import {
  Check,
  Loader2,
  LogOut,
  MapPin,
  RotateCcw,
  User,
  X,
} from 'lucide-react'
import { ArgentinaProvinces3DMap } from './ArgentinaProvinces3DMap'
import { BrandBlock } from './BrandBlock'
import {
  PAMPEAN_PROVINCE_IDS,
  getProvinceById,
} from '../utils/geo'

interface ProvinceSelectorScreenProps {
  /** Selección inicial (p. ej. al volver a editar el filtro). */
  initialSelected: string[]
  isSaving: boolean
  errorMsg: string | null
  isDemo: boolean
  userLabel?: string
  onApply: (provinceIds: string[]) => void
  onLogout: () => void
}

export function ProvinceSelectorScreen({
  initialSelected,
  isSaving,
  errorMsg,
  isDemo,
  userLabel,
  onApply,
  onLogout,
}: ProvinceSelectorScreenProps) {
  const [selected, setSelected] = useState<string[]>(() =>
    initialSelected.filter((id) =>
      (PAMPEAN_PROVINCE_IDS as readonly string[]).includes(id)
    )
  )

  const toggleProvince = (id: string) => {
    if (isSaving) return
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    )
  }

  const canApply = selected.length > 0 && !isSaving
  const totalEnabled = PAMPEAN_PROVINCE_IDS.length

  return (
    <div className="province-screen">
      <header className="top-navbar">
        <BrandBlock />
        <div className="header-session-bar">
          {isDemo ? (
            <span className="header-demo-pill">Modo demo</span>
          ) : (
            <span className="header-user-pill">
              <User size={14} aria-hidden="true" />
              <span>{userLabel || 'Mi cuenta'}</span>
            </span>
          )}
          <button
            type="button"
            className="header-session-btn"
            onClick={onLogout}
            disabled={isSaving}
          >
            <LogOut size={14} aria-hidden="true" />
            <span>{isDemo ? 'Salir del modo demo' : 'Cerrar sesión'}</span>
          </button>
        </div>
      </header>

      <main className="province-main">
        <section className="province-map-area" aria-label="Mapa de Argentina">
          <ArgentinaProvinces3DMap
            selected={selected}
            disabled={isSaving}
            onToggleProvince={toggleProvince}
          />
        </section>

        <aside className="right-analysis-pane" aria-label="Resumen de selección">
          <div className="right-folder-body province-folder-body">
            <section className="panel-section province-selector-card">
              <div className="province-card-top">
                <div className="section-header-row">
                  <h2 className="section-title">Selección de región</h2>
                  <span className="coords-pill" aria-live="polite">
                    <code>
                      {selected.length}/{totalEnabled}
                    </code>
                    <span className="coords-ha">provincias</span>
                  </span>
                </div>

                <p className="province-panel-text">
                  Cobertura habilitada para la Región Pampeana. Seleccione en el
                  mapa las provincias donde se ubican sus campos.
                </p>
              </div>

              <div className="province-selection-body">
                <div className="control-group">
                  <div className="province-control-header">
                    <span className="control-label">
                      <MapPin size={14} aria-hidden="true" />
                      <span>Provincias incluidas</span>
                    </span>
                    <button
                      type="button"
                      className="reset-whatif-btn province-reset-btn"
                      disabled={selected.length === 0 || isSaving}
                      onClick={() => setSelected([])}
                    >
                      <RotateCcw size={13} aria-hidden="true" />
                      <span>Limpiar selección</span>
                    </button>
                  </div>

                  <div
                    className={`what-if-box province-selection-box ${
                      selected.length === 0 ? 'is-empty' : ''
                    }`}
                  >
                    {selected.length === 0 ? (
                      <p className="empty-rotation-text">
                        Aún no hay provincias seleccionadas. Seleccione al menos una
                        jurisdicción en el mapa.
                      </p>
                    ) : (
                      <ul className="province-chip-list">
                        {selected.map((id) => (
                          <li key={id}>
                            <button
                              type="button"
                              className="province-chip"
                              onClick={() => toggleProvince(id)}
                              disabled={isSaving}
                              aria-label={`Quitar ${getProvinceById(id)?.properties.nombre ?? id}`}
                            >
                              <Check size={13} aria-hidden="true" />
                              <span>{getProvinceById(id)?.properties.nombre ?? id}</span>
                              <X size={13} aria-hidden="true" />
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>

                {errorMsg && (
                  <div className="province-panel-error" role="alert">
                    {errorMsg}
                  </div>
                )}
              </div>

              <div className="province-card-actions">
                <div className="plan-action-footer">
                  <span className="plan-status-hint">
                    {selected.length === 0
                      ? 'Seleccione al menos una provincia.'
                      : 'El mapa climático filtrará los campos de esta área.'}
                  </span>
                  <button
                    type="button"
                    className="plan-submit-btn"
                    disabled={!canApply}
                    onClick={() => onApply(selected)}
                  >
                    {isSaving ? (
                      <>
                        <Loader2 size={16} className="province-spin" aria-hidden="true" />
                        <span>Guardando...</span>
                      </>
                    ) : (
                      <span>Aplicar y continuar</span>
                    )}
                  </button>
                </div>
              </div>
            </section>

            <section
              className="panel-section empty-rotation-card what-if-standalone-section province-coverage-card"
              aria-label="Alcance geográfico"
            >
              <span className="section-eyebrow">Cobertura territorial actual</span>
              <p className="empty-rotation-text">
                Habilitadas: Buenos Aires, Córdoba, Entre Ríos, La Pampa y Santa
                Fe. Puede elegir más de una si un campo cruza un límite
                provincial; el resto permanece en expansión.
              </p>
            </section>
          </div>
        </aside>
      </main>
    </div>
  )
}
