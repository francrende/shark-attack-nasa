import { useEffect, useState, type FormEvent } from 'react'
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Eye,
  EyeOff,
  Globe,
  Lock,
  LogOut,
  Mail,
  MapPin,
  Maximize2,
  MoreVertical,
  Save,
  User,
  X,
} from 'lucide-react'
import { updateCurrentUser } from '../services/authClient'
import { getFieldColorByIndex } from '../theme/mapColors'
import type { UserField, UserProfile, UserUpdateRequest } from '../types/api'

type SettingsTabId = 'usuario' | 'campos' | 'expandir_mapa' | 'idioma'

interface UserSettingsModalProps {
  isOpen: boolean
  user: UserProfile | null
  accessToken: string | null
  fields: UserField[]
  onClose: () => void
  onUserUpdated: (user: UserProfile) => void
  onRenameField: (fieldId: string, nombre: string) => Promise<void>
  onEditFieldPolygon: (field: UserField) => void
  onDeleteField: (fieldId: string) => Promise<void>
  onLogout: () => void
}

const PLACEHOLDER_TABS: {
  id: Exclude<SettingsTabId, 'usuario' | 'campos'>
  label: string
  icon: typeof Globe
  placeholder: string
}[] = [
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

const ALL_TABS: {
  id: SettingsTabId
  label: string
  icon: typeof User
}[] = [
  { id: 'usuario', label: 'Usuario', icon: User },
  { id: 'campos', label: 'Campos', icon: MapPin },
  ...PLACEHOLDER_TABS.map(({ id, label, icon }) => ({ id, label, icon })),
]

export function UserSettingsModal({
  isOpen,
  user,
  accessToken,
  fields,
  onClose,
  onUserUpdated,
  onRenameField,
  onEditFieldPolygon,
  onDeleteField,
  onLogout,
}: UserSettingsModalProps) {
  const [activeTab, setActiveTab] = useState<SettingsTabId>('usuario')
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const [editingFieldId, setEditingFieldId] = useState<string | null>(null)
  const [editingFieldName, setEditingFieldName] = useState('')
  const [confirmDeleteFieldId, setConfirmDeleteFieldId] = useState<string | null>(
    null
  )
  const [openMenu, setOpenMenu] = useState<{
    field: UserField
    top: number
    right: number
    openUp: boolean
  } | null>(null)
  const [busyFieldId, setBusyFieldId] = useState<string | null>(null)
  const [fieldsError, setFieldsError] = useState<string | null>(null)
  const [fieldsSuccess, setFieldsSuccess] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setNombre(user?.nombre ?? '')
    setEmail(user?.email ?? '')
    setPassword('')
    setShowPassword(false)
    setErrorMsg(null)
    setSuccessMsg(null)
    setEditingFieldId(null)
    setEditingFieldName('')
    setConfirmDeleteFieldId(null)
    setOpenMenu(null)
    setBusyFieldId(null)
    setFieldsError(null)
    setFieldsSuccess(null)
  }, [isOpen, user])

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (openMenu) {
          setOpenMenu(null)
          return
        }
        if (editingFieldId) {
          setEditingFieldId(null)
          setEditingFieldName('')
          return
        }
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, openMenu, editingFieldId, onClose])

  useEffect(() => {
    if (!openMenu) return
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (
        target?.closest('.settings-field-menu') ||
        target?.closest('.settings-menu-trigger')
      ) {
        return
      }
      setOpenMenu(null)
    }
    window.addEventListener('mousedown', handlePointerDown)
    return () => window.removeEventListener('mousedown', handlePointerDown)
  }, [openMenu])

  if (!isOpen) return null

  const trimmedName = nombre.trim()
  const trimmedEmail = email.trim()
  const hasChanges =
    trimmedName !== (user?.nombre ?? '').trim() ||
    trimmedEmail !== (user?.email ?? '').trim() ||
    password.length > 0

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setErrorMsg(null)
    setSuccessMsg(null)

    if (!trimmedName) {
      setErrorMsg('Ingrese su nombre completo.')
      return
    }
    if (!trimmedEmail || !trimmedEmail.includes('@')) {
      setErrorMsg('Ingrese un correo electrónico válido.')
      return
    }
    if (password.length > 0 && password.length < 6) {
      setErrorMsg('La nueva contraseña debe tener al menos 6 caracteres.')
      return
    }
    if (!accessToken) {
      setErrorMsg('La sesión no se encuentra activa. Inicie sesión nuevamente.')
      return
    }

    const payload: UserUpdateRequest = {}
    if (trimmedName !== (user?.nombre ?? '').trim()) {
      payload.nombre = trimmedName
    }
    if (trimmedEmail !== (user?.email ?? '').trim()) {
      payload.email = trimmedEmail
    }
    if (password.length > 0) {
      payload.password = password
    }

    setIsSaving(true)
    try {
      const updated = await updateCurrentUser(accessToken, payload)
      onUserUpdated({
        id: updated.id || user?.id || '',
        nombre: updated.nombre || trimmedName,
        email: updated.email || trimmedEmail,
        created_at: updated.created_at ?? user?.created_at,
      })
      setPassword('')
      setSuccessMsg('Los datos de su cuenta se actualizaron correctamente.')
    } catch (err) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : 'No fue posible actualizar los datos de su cuenta.'
      )
    } finally {
      setIsSaving(false)
    }
  }

  const handleStartRename = (field: UserField) => {
    setConfirmDeleteFieldId(null)
    setFieldsError(null)
    setFieldsSuccess(null)
    setEditingFieldId(field.id)
    setEditingFieldName(field.nombre)
  }

  const handleCancelRename = () => {
    setEditingFieldId(null)
    setEditingFieldName('')
  }

  const handleSubmitRename = async (
    event: FormEvent<HTMLFormElement>,
    field: UserField
  ) => {
    event.preventDefault()
    const trimmed = editingFieldName.trim()
    setFieldsError(null)
    setFieldsSuccess(null)

    if (!trimmed) {
      setFieldsError('Ingrese un nombre válido para el campo.')
      return
    }
    if (trimmed === field.nombre.trim()) {
      handleCancelRename()
      return
    }

    setBusyFieldId(field.id)
    try {
      await onRenameField(field.id, trimmed)
      setEditingFieldId(null)
      setEditingFieldName('')
      setFieldsSuccess('El nombre del campo se actualizó correctamente.')
    } catch (err) {
      setFieldsError(
        err instanceof Error
          ? err.message
          : 'No fue posible actualizar el nombre del campo.'
      )
    } finally {
      setBusyFieldId(null)
    }
  }

  const handleConfirmDelete = async (field: UserField) => {
    setFieldsError(null)
    setFieldsSuccess(null)
    setBusyFieldId(field.id)
    try {
      await onDeleteField(field.id)
      setConfirmDeleteFieldId(null)
      if (editingFieldId === field.id) {
        setEditingFieldId(null)
        setEditingFieldName('')
      }
      setFieldsSuccess(`Se eliminó el campo "${field.nombre}".`)
    } catch (err) {
      setFieldsError(
        err instanceof Error
          ? err.message
          : 'No fue posible eliminar el campo.'
      )
    } finally {
      setBusyFieldId(null)
    }
  }

  const activePlaceholder = PLACEHOLDER_TABS.find((tab) => tab.id === activeTab)

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
            {ALL_TABS.map((tab) => {
              const Icon = tab.icon
              const isActive = tab.id === activeTab
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  className={`settings-folder-tab ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    setOpenMenu(null)
                    setActiveTab(tab.id)
                  }}
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
          {activeTab === 'usuario' ? (
            <div className="settings-placeholder-card">
              <div className="settings-placeholder-head">
                <User size={18} aria-hidden="true" />
                <h2>Cuenta de usuario</h2>
              </div>

              {errorMsg && (
                <div className="settings-alert settings-alert-error" role="alert">
                  <AlertCircle size={15} aria-hidden="true" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {successMsg && (
                <div className="settings-alert settings-alert-success" role="status">
                  <CheckCircle2 size={15} aria-hidden="true" />
                  <span>{successMsg}</span>
                </div>
              )}

              <form className="settings-form" onSubmit={handleSubmit} noValidate>
                <div className="settings-field">
                  <label className="settings-label" htmlFor="settings-nombre">
                    Nombre completo
                  </label>
                  <div className="settings-input-wrap">
                    <User size={15} className="settings-input-icon" aria-hidden="true" />
                    <input
                      id="settings-nombre"
                      type="text"
                      className="settings-input"
                      placeholder="Nombre del productor o asesor"
                      value={nombre}
                      onChange={(e) => setNombre(e.target.value)}
                      autoComplete="name"
                      disabled={isSaving}
                      required
                    />
                  </div>
                </div>

                <div className="settings-field">
                  <label className="settings-label" htmlFor="settings-email">
                    Correo electrónico
                  </label>
                  <div className="settings-input-wrap">
                    <Mail size={15} className="settings-input-icon" aria-hidden="true" />
                    <input
                      id="settings-email"
                      type="email"
                      className="settings-input"
                      placeholder="productor@campo.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="email"
                      disabled={isSaving}
                      required
                    />
                  </div>
                </div>

                <div className="settings-field">
                  <label className="settings-label" htmlFor="settings-password">
                    Nueva contraseña
                  </label>
                  <div className="settings-input-wrap">
                    <Lock size={15} className="settings-input-icon" aria-hidden="true" />
                    <input
                      id="settings-password"
                      type={showPassword ? 'text' : 'password'}
                      className="settings-input has-toggle"
                      placeholder="Dejar vacío para conservar la actual"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="new-password"
                      disabled={isSaving}
                    />
                    <button
                      type="button"
                      className="settings-eye-btn"
                      onClick={() => setShowPassword((prev) => !prev)}
                      aria-label={
                        showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'
                      }
                    >
                      {showPassword ? (
                        <EyeOff size={15} aria-hidden="true" />
                      ) : (
                        <Eye size={15} aria-hidden="true" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="settings-actions-row">
                  <button
                    type="button"
                    className="settings-logout-btn"
                    onClick={onLogout}
                    disabled={isSaving}
                  >
                    <LogOut size={15} aria-hidden="true" />
                    <span>Cerrar sesión</span>
                  </button>

                  <button
                    type="submit"
                    className="settings-save-btn"
                    disabled={!hasChanges || isSaving}
                  >
                    <Save size={15} aria-hidden="true" />
                    <span>{isSaving ? 'Guardando...' : 'Guardar cambios'}</span>
                  </button>
                </div>
              </form>
            </div>
          ) : activeTab === 'campos' ? (
            <div className="settings-placeholder-card">
              <div className="settings-placeholder-head">
                <MapPin size={18} aria-hidden="true" />
                <h2>Campos registrados</h2>
              </div>

              {fieldsError && (
                <div className="settings-alert settings-alert-error" role="alert">
                  <AlertCircle size={15} aria-hidden="true" />
                  <span>{fieldsError}</span>
                </div>
              )}

              {fieldsSuccess && (
                <div className="settings-alert settings-alert-success" role="status">
                  <CheckCircle2 size={15} aria-hidden="true" />
                  <span>{fieldsSuccess}</span>
                </div>
              )}

              {fields.length === 0 ? (
                <p className="settings-placeholder-text">
                  No hay campos registrados en esta cuenta. Utilice «Nuevo campo» en la barra superior del mapa para delimitar uno.
                </p>
              ) : (
                <ul
                  className="settings-fields-list"
                  onScroll={() => {
                    if (openMenu) setOpenMenu(null)
                  }}
                >
                  {fields.map((field, idx) => {
                    const isEditing = editingFieldId === field.id
                    const isConfirmingDelete = confirmDeleteFieldId === field.id
                    const isBusy = busyFieldId === field.id
                    const { hex: dotColor } = getFieldColorByIndex(idx)
                    const metaLabel =
                      field.hectareas !== null
                        ? `${Math.round(field.hectareas)} ha`
                        : `${field.lat.toFixed(3)}, ${field.lon.toFixed(3)}`

                    return (
                      <li key={field.id} className="settings-field-row">
                        {isEditing ? (
                          <form
                            className="settings-inline-rename-form"
                            onSubmit={(event) => handleSubmitRename(event, field)}
                          >
                            <span
                              className="settings-field-dot"
                              style={{ backgroundColor: dotColor }}
                              aria-hidden="true"
                            />
                            <input
                              type="text"
                              className="settings-inline-input"
                              value={editingFieldName}
                              onChange={(event) => setEditingFieldName(event.target.value)}
                              aria-label="Nuevo nombre del campo"
                              maxLength={120}
                              disabled={isBusy}
                              autoFocus
                            />
                            <div className="settings-field-actions">
                              <button
                                type="submit"
                                className="settings-icon-btn confirm"
                                aria-label="Guardar nombre"
                                title="Guardar nombre"
                                disabled={isBusy}
                              >
                                <Check size={14} aria-hidden="true" />
                              </button>
                              <button
                                type="button"
                                className="settings-icon-btn"
                                aria-label="Cancelar edición"
                                title="Cancelar"
                                disabled={isBusy}
                                onClick={handleCancelRename}
                              >
                                <X size={14} aria-hidden="true" />
                              </button>
                            </div>
                          </form>
                        ) : (
                          <>
                            <div className="settings-field-main">
                              <span
                                className="settings-field-dot"
                                style={{ backgroundColor: dotColor }}
                                aria-hidden="true"
                              />
                              <div className="settings-field-info">
                                <span className="settings-field-name">{field.nombre}</span>
                                <span className="settings-field-meta">{metaLabel}</span>
                              </div>
                            </div>

                            {isConfirmingDelete ? (
                              <div className="settings-delete-confirm">
                                <button
                                  type="button"
                                  className="settings-confirm-delete-btn"
                                  disabled={isBusy}
                                  onClick={() => handleConfirmDelete(field)}
                                >
                                  {isBusy ? 'Eliminando...' : 'Eliminar'}
                                </button>
                                <button
                                  type="button"
                                  className="settings-cancel-delete-btn"
                                  disabled={isBusy}
                                  onClick={() => setConfirmDeleteFieldId(null)}
                                >
                                  Cancelar
                                </button>
                              </div>
                            ) : (
                              <div className="settings-field-actions">
                                <button
                                  type="button"
                                  className={`settings-icon-btn settings-menu-trigger ${
                                    openMenu?.field.id === field.id ? 'active' : ''
                                  }`}
                                  aria-label={`Opciones de ${field.nombre}`}
                                  aria-haspopup="menu"
                                  aria-expanded={openMenu?.field.id === field.id}
                                  title="Opciones"
                                  disabled={isBusy}
                                  onClick={(event) => {
                                    if (openMenu?.field.id === field.id) {
                                      setOpenMenu(null)
                                      return
                                    }
                                    const rect =
                                      event.currentTarget.getBoundingClientRect()
                                    const openUp =
                                      rect.bottom + 140 > window.innerHeight
                                    setOpenMenu({
                                      field,
                                      top: openUp
                                        ? rect.top - 4
                                        : rect.bottom + 4,
                                      right: Math.max(
                                        12,
                                        window.innerWidth - rect.right
                                      ),
                                      openUp,
                                    })
                                  }}
                                >
                                  <MoreVertical size={15} aria-hidden="true" />
                                </button>
                              </div>
                            )}
                          </>
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}

              {openMenu && (
                <div
                  className={`settings-field-menu ${openMenu.openUp ? 'open-up' : ''}`}
                  role="menu"
                  aria-label={`Acciones para ${openMenu.field.nombre}`}
                  style={{
                    top: `${openMenu.top}px`,
                    right: `${openMenu.right}px`,
                  }}
                >
                  <button
                    type="button"
                    role="menuitem"
                    className="settings-field-menu-item rename"
                    onClick={() => {
                      const target = openMenu.field
                      setOpenMenu(null)
                      handleStartRename(target)
                    }}
                  >
                    Editar nombre
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className="settings-field-menu-item polygon"
                    onClick={() => {
                      const target = openMenu.field
                      setOpenMenu(null)
                      onEditFieldPolygon(target)
                    }}
                  >
                    Editar superficie
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className="settings-field-menu-item danger"
                    onClick={() => {
                      const target = openMenu.field
                      setOpenMenu(null)
                      setEditingFieldId(null)
                      setFieldsError(null)
                      setFieldsSuccess(null)
                      setConfirmDeleteFieldId(target.id)
                    }}
                  >
                    Borrar
                  </button>
                </div>
              )}
            </div>
          ) : (
            activePlaceholder && (
              <div className="settings-placeholder-card">
                <div className="settings-placeholder-head">
                  <activePlaceholder.icon size={18} aria-hidden="true" />
                  <h2>{activePlaceholder.label}</h2>
                </div>
                <p className="settings-placeholder-text">
                  {activePlaceholder.placeholder}
                </p>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  )
}
