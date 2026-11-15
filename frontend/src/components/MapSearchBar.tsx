import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import { Loader2, MapPin, MoreVertical, Search, X } from 'lucide-react'
import {
  parseCoordinateQuery,
  searchMapLocations,
  type MapSearchResult,
} from '../services/geocodeClient'

interface MapSearchBarProps {
  selectedProvinces: string[]
  isDemo: boolean
  isUserSettingsOpen: boolean
  onUserAction: () => void
  onSelectLocation: (result: MapSearchResult) => void
}

export function MapSearchBar({
  selectedProvinces,
  isDemo,
  isUserSettingsOpen,
  onUserAction,
  onSelectLocation,
}: MapSearchBarProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<MapSearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)

  const containerRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const lastFetchedQueryRef = useRef('')
  const lastSelectedResultRef = useRef<MapSearchResult | null>(null)

  const cancelInFlight = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
  }, [])

  useEffect(() => {
    return () => cancelInFlight()
  }, [cancelInFlight])

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [])

  const runSearch = useCallback(
    async (rawText: string, autoPickFirst: boolean) => {
      const trimmed = rawText.trim()
      if (!trimmed) return

      cancelInFlight()
      const controller = new AbortController()
      abortRef.current = controller

      setIsSearching(true)
      setSearchError(null)
      setIsDropdownOpen(true)

      try {
        const found = await searchMapLocations(
          trimmed,
          selectedProvinces,
          controller.signal
        )
        if (controller.signal.aborted) return

        lastFetchedQueryRef.current = trimmed
        setResults(found)
        setHasSearched(true)
        setActiveIndex(found.length > 0 ? 0 : -1)

        if (autoPickFirst && found.length > 0) {
          lastSelectedResultRef.current = found[0]
          lastFetchedQueryRef.current = found[0].label
          onSelectLocation(found[0])
          setQuery(found[0].label)
          setIsDropdownOpen(false)
        }
      } catch (err) {
        if (controller.signal.aborted) return
        setResults([])
        setHasSearched(true)
        setSearchError(
          err instanceof Error
            ? err.message
            : 'No fue posible buscar la ubicación. Intente nuevamente.'
        )
      } finally {
        if (!controller.signal.aborted) {
          setIsSearching(false)
        }
      }
    },
    [cancelInFlight, onSelectLocation, selectedProvinces]
  )

  useEffect(() => {
    const trimmed = query.trim()
    if (trimmed.length < 3 || trimmed === lastFetchedQueryRef.current) {
      return
    }

    const coordMatch = parseCoordinateQuery(trimmed, selectedProvinces)
    if (coordMatch) {
      const timer = window.setTimeout(() => {
        setResults([coordMatch])
        setHasSearched(true)
        setSearchError(null)
        setIsDropdownOpen(true)
        setActiveIndex(0)
        lastFetchedQueryRef.current = trimmed
      }, 120)
      return () => window.clearTimeout(timer)
    }

    const timer = window.setTimeout(() => {
      void runSearch(trimmed, false)
    }, 450)

    return () => window.clearTimeout(timer)
  }, [query, runSearch, selectedProvinces])

  const handleChooseResult = (result: MapSearchResult) => {
    lastSelectedResultRef.current = result
    lastFetchedQueryRef.current = result.label
    setQuery(result.label)
    setIsDropdownOpen(false)
    setSearchError(null)
    onSelectLocation(result)
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) {
      inputRef.current?.focus()
      return
    }

    if (
      lastSelectedResultRef.current &&
      lastSelectedResultRef.current.label === trimmed
    ) {
      handleChooseResult(lastSelectedResultRef.current)
      return
    }

    if (
      isDropdownOpen &&
      trimmed === lastFetchedQueryRef.current &&
      results.length > 0
    ) {
      const target = results[activeIndex >= 0 ? activeIndex : 0]
      if (target) {
        handleChooseResult(target)
        return
      }
    }

    void runSearch(trimmed, true)
  }

  const handleClear = () => {
    cancelInFlight()
    lastSelectedResultRef.current = null
    lastFetchedQueryRef.current = ''
    setQuery('')
    setResults([])
    setHasSearched(false)
    setSearchError(null)
    setIsSearching(false)
    setIsDropdownOpen(false)
    setActiveIndex(-1)
    inputRef.current?.focus()
  }

  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setIsDropdownOpen(false)
      return
    }
    if (!isDropdownOpen || results.length === 0) return

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((prev) => (prev + 1) % results.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((prev) => (prev <= 0 ? results.length - 1 : prev - 1))
    }
  }

  const showDropdown =
    isDropdownOpen &&
    (isSearching || searchError !== null || results.length > 0 || hasSearched)

  return (
    <div ref={containerRef} className="map-search-wrap">
      <form
        className="map-search-pill"
        role="search"
        aria-label="Buscar ubicaciones en el mapa"
        onSubmit={handleSubmit}
      >
        <button
          type="button"
          className={`map-search-menu-btn ${isUserSettingsOpen ? 'active' : ''}`}
          onClick={onUserAction}
          title={isDemo ? 'Iniciar sesión' : 'Ajustes de usuario'}
          aria-label={isDemo ? 'Iniciar sesión' : 'Ajustes de usuario'}
        >
          <MoreVertical size={16} aria-hidden="true" />
        </button>

        <input
          ref={inputRef}
          type="text"
          className="map-search-input"
          value={query}
          onChange={(event) => {
            const nextVal = event.target.value
            setQuery(nextVal)
            setSearchError(null)
            if (!nextVal.trim()) {
              cancelInFlight()
              lastFetchedQueryRef.current = ''
              setResults([])
              setHasSearched(false)
              setIsSearching(false)
              setIsDropdownOpen(false)
            }
          }}
          onFocus={() => {
            if (results.length > 0 || searchError) {
              setIsDropdownOpen(true)
            }
          }}
          onKeyDown={handleInputKeyDown}
          placeholder="Buscar ubicación..."
          aria-label="Buscar localidad o coordenadas en el mapa"
          aria-expanded={showDropdown}
          aria-autocomplete="list"
        />

        {query.length > 0 && (
          <button
            type="button"
            className="map-search-clear-btn"
            onClick={handleClear}
            aria-label="Limpiar búsqueda"
            title="Limpiar búsqueda"
          >
            <X size={13} aria-hidden="true" />
          </button>
        )}

        <button
          type="submit"
          className="map-search-submit-btn"
          aria-label="Buscar ubicación"
          title="Buscar ubicación"
        >
          {isSearching ? (
            <Loader2 size={15} className="province-spin" aria-hidden="true" />
          ) : (
            <Search size={15} aria-hidden="true" />
          )}
        </button>
      </form>

      {showDropdown && (
        <div
          className="map-search-dropdown"
          role="listbox"
          aria-label="Resultados de ubicación"
        >
          {isSearching && (
            <div className="map-search-status">Buscando ubicaciones...</div>
          )}

          {!isSearching && searchError && (
            <div className="map-search-status error" role="alert">
              {searchError}
            </div>
          )}

          {!isSearching &&
            !searchError &&
            hasSearched &&
            results.length === 0 && (
              <div className="map-search-status">
                No se encontraron ubicaciones.
              </div>
            )}

          {!isSearching &&
            !searchError &&
            results.map((item, idx) => (
              <button
                key={item.id}
                type="button"
                role="option"
                aria-selected={idx === activeIndex}
                className={`map-search-option ${idx === activeIndex ? 'active' : ''}`}
                onClick={() => handleChooseResult(item)}
              >
                <MapPin
                  size={14}
                  className="map-search-option-icon"
                  aria-hidden="true"
                />
                <span className="map-search-option-text">
                  <span className="map-search-option-title">{item.label}</span>
                  <span className="map-search-option-sub">
                    {item.secondaryLabel}
                  </span>
                </span>
              </button>
            ))}
        </div>
      )}
    </div>
  )
}
