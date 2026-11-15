import { useState, type FormEvent } from 'react'
import {
  AlertCircle,
  Compass,
  Eye,
  EyeOff,
  Lock,
  Mail,
  User,
} from 'lucide-react'
import {
  extractUserFromAuthResponse,
  fetchCurrentUser,
  loginUser,
  registerUser,
  setStoredAuthToken,
  setStoredRefreshToken,
} from '../services/authClient'
import type { UserProfile } from '../types/api'

type AuthMode = 'login' | 'register'

interface AuthScreenProps {
  initialError?: string | null
  onAuthenticated: (user: UserProfile, token: string) => void
  onEnterDemo: () => void
}

export function AuthScreen({
  initialError = null,
  onAuthenticated,
  onEnterDemo,
}: AuthScreenProps) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(initialError)
  const [infoMsg, setInfoMsg] = useState<string | null>(null)

  const handleSwitchMode = (nextMode: AuthMode) => {
    setMode(nextMode)
    setErrorMsg(null)
    setInfoMsg(null)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setErrorMsg(null)
    setInfoMsg(null)

    const cleanEmail = email.trim()
    const cleanName = nombre.trim()

    if (mode === 'register' && !cleanName) {
      setErrorMsg('Ingrese su nombre completo para crear la cuenta.')
      return
    }
    if (!cleanEmail) {
      setErrorMsg('Ingrese su correo electrónico.')
      return
    }
    if (password.length < 6) {
      setErrorMsg('La contraseña debe tener al menos 6 caracteres.')
      return
    }

    setIsSubmitting(true)
    try {
      const response =
        mode === 'login'
          ? await loginUser({ email: cleanEmail, password })
          : await registerUser({
            email: cleanEmail,
            password,
            nombre: cleanName,
          })

      if (response.requiere_confirmacion_email || !response.access_token) {
        setInfoMsg(
          'Cuenta creada correctamente. Verifique su correo electrónico e inicie sesión.'
        )
        setMode('login')
        setPassword('')
        return
      }

      setStoredAuthToken(response.access_token)
      if (response.refresh_token) {
        setStoredRefreshToken(response.refresh_token)
      }
      let user = extractUserFromAuthResponse(response, cleanEmail, cleanName)
      try {
        user = await fetchCurrentUser(response.access_token)
      } catch {
        // Si /me no está disponible inmediatamente, conservar los datos de la respuesta de auth
      }

      onAuthenticated(user, response.access_token)
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'No fue posible completar la solicitud.'
      setErrorMsg(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="auth-shell">
      <section
        className="auth-notebook-pane"
        aria-label="Presentación de Ereia"
      >
        <div className="auth-notebook-brand">
          <div className="auth-notebook-logo-row">
            <img
              src="/ereia-icon.png"
              alt="Logo de Ereia"
              className="auth-notebook-logo"
            />
            <h1 className="auth-notebook-wordmark">
              <span className="brand-wordmark-ere">Ere</span>
              <span className="brand-wordmark-ia">ia</span>
            </h1>
          </div>
          <p className="auth-notebook-tagline">Soporte para el cultivo</p>
        </div>
      </section>

      <main className="auth-main">
        <section className="auth-card" aria-labelledby="auth-heading">
          <div className="auth-card-header">

            <h2 id="auth-heading" className="auth-title">
              {mode === 'login'
                ? 'Acceso a sus lotes'
                : 'Registro de productor'}
            </h2>
            <p className="auth-description">
              {mode === 'login'
                ? 'Inicie sesión para consultar sus lotes, campañas históricas y simulaciones.'
                : 'Cree su cuenta para guardar sus lotes, cultivos previos y resultados de campaña.'}
            </p>
          </div>

          <div className="auth-mode-switch" role="tablist" aria-label="Tipo de acceso">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'login'}
              className={`auth-mode-btn ${mode === 'login' ? 'active' : ''}`}
              onClick={() => handleSwitchMode('login')}
            >
              Iniciar sesión
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'register'}
              className={`auth-mode-btn ${mode === 'register' ? 'active' : ''}`}
              onClick={() => handleSwitchMode('register')}
            >
              Crear cuenta
            </button>
          </div>

          {errorMsg && (
            <div className="auth-alert auth-alert-error" role="alert">
              <AlertCircle size={16} aria-hidden="true" />
              <span>{errorMsg}</span>
            </div>
          )}

          {infoMsg && (
            <div className="auth-alert auth-alert-info" role="status">
              <span>{infoMsg}</span>
            </div>
          )}

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            {mode === 'register' && (
              <div className="auth-field">
                <label className="auth-label" htmlFor="auth-nombre">
                  Nombre completo
                </label>
                <div className="auth-input-wrap">
                  <User size={16} className="auth-input-icon" aria-hidden="true" />
                  <input
                    id="auth-nombre"
                    type="text"
                    className="auth-input"
                    placeholder="Ej. María González"
                    value={nombre}
                    onChange={(e) => setNombre(e.target.value)}
                    autoComplete="name"
                    disabled={isSubmitting}
                    required
                  />
                </div>
              </div>
            )}

            <div className="auth-field">
              <label className="auth-label" htmlFor="auth-email">
                Correo electrónico
              </label>
              <div className="auth-input-wrap">
                <Mail size={16} className="auth-input-icon" aria-hidden="true" />
                <input
                  id="auth-email"
                  type="email"
                  className="auth-input"
                  placeholder="productor@campo.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  disabled={isSubmitting}
                  required
                />
              </div>
            </div>

            <div className="auth-field">
              <label className="auth-label" htmlFor="auth-password">
                Contraseña
              </label>
              <div className="auth-input-wrap">
                <Lock size={16} className="auth-input-icon" aria-hidden="true" />
                <input
                  id="auth-password"
                  type={showPassword ? 'text' : 'password'}
                  className="auth-input auth-input-password"
                  placeholder="Mínimo 6 caracteres"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={
                    mode === 'login' ? 'current-password' : 'new-password'
                  }
                  disabled={isSubmitting}
                  required
                />
                <button
                  type="button"
                  className="auth-toggle-password"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={
                    showPassword
                      ? 'Ocultar contraseña'
                      : 'Mostrar contraseña'
                  }
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? mode === 'login'
                  ? 'Ingresando...'
                  : 'Creando cuenta...'
                : mode === 'login'
                  ? 'Iniciar sesión'
                  : 'Crear cuenta'}
            </button>
          </form>

          {mode === 'login' && (
            <>
              <div className="auth-divider">
                <span>o bien</span>
              </div>

              <button
                type="button"
                className="auth-demo-btn"
                onClick={onEnterDemo}
                disabled={isSubmitting}
              >
                <Compass size={16} aria-hidden="true" />
                <span>Explorar en modo demo</span>
              </button>
            </>
          )}
        </section>
      </main>
    </div>
  )
}
