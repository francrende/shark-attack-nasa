import { useEffect, useState } from 'react'
import { Globe, MapPin, Maximize2, User, X } from 'lucide-react'
import type { UserProfile } from '../types/api'

type SettingsTabId = 'usuario' | 'campos' | 'expandir_mapa' | 'idioma'

interface UserSettingsModalProps {
  isOpen: boolean
  user: UserProfile | null
  onClose: () => void
}

const SETTINGS_TABS: {
  id: SettingsTabId
  label: string
  icon: typeof User
  placeholder: string
}[] = [
  {
    id: 'usuario',
    label: 'Usuario',
    icon: User,
    placeholder:
      'Las opciones de perfil y cuenta del productor se completarán en la próxima etapa.',
  },
  {
    id: 'campos',
    label: 'Campos',
    icon: MapPin,
    placeholder:
      'El listado para renombrar, borrar campos y consultar sus campañas se completará en la próxima etapa.',
  },
  {
    id: 'expandir_mapa',
    label: 'Expandir mapa',
    icon: Maximize2,
    placeholder:
      'El control para ampliar el visor del mapa a pantalla completa se completará en la próxima etapa.',
  },
  {
    id: 'idioma',
    label: 'Idioma',
    icon: Globe,
    placeholder:
      'La selección de idioma de la interfaz se completará en la próxima etapa.',
  },
]

export function UserSettingsModal({
  isOpen,
  user,
  onClose,
}: UserSettingsModalProps) {
  const [activeTab, setActiveTab] = useState<SettingsTabId>('usuario')

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const currentTab =
    SETTINGS_TABS.find((tab) => tab.id === activeTab) ?? SETTINGS_TABS[0]
  const ActiveIcon = currentTab.icon

  return (
    <div
      className="settings-glass-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Ajustes de usuario"
      onClick={onClose}
    >
      <div
        className="settings-folder-shell"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="settings-folder-header-row">
          <nav
            className="settings-folder-tabs"
            role="tablist"
            aria-label="Secciones de ajustes"
          >
            {SETTINGS_TABS.map((tab) => {
              const Icon = tab.icon
              const isActive = tab.id === activeTab
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  className={`settings-folder-tab ${isActive ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  <Icon size={14} aria-hidden="true" />
                  <span>{tab.label}</span>
                </button>
              )
            })}
          </nav>

          <button
            type="button"
            className="settings-close-btn"
            aria-label="Cerrar ajustes"
            onClick={onClose}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        <div className="settings-folder-body" role="tabpanel">
          <div className="settings-placeholder-card">
            <div className="settings-placeholder-head">
              <ActiveIcon size={18} aria-hidden="true" />
              <h2>{currentTab.label}</h2>
            </div>

            {activeTab === 'usuario' && user && (
              <p className="settings-user-summary">
                Sesión iniciada como{' '}
                <strong>{user.nombre || user.email}</strong>
                {user.email ? ` (${user.email})` : ''}.
              </p>
            )}

            <p className="settings-placeholder-text">
              {currentTab.placeholder}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
