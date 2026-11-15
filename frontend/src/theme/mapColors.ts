/**
 * Constantes de color sincronizadas con los tokens CSS de `src/index.css`.
 * Se usan únicamente donde las APIs de terceros (Leaflet `pathOptions`, gradientes dinámicos o SVG)
 * requieren valores de color en JavaScript.
 */
export const THEME_COLORS = {
  primary: '#4B5B2D',
  primaryDark: '#35421E',
  primaryDarker: '#252F14',
  primarySoft: 'rgba(75, 91, 45, 0.16)',
  bg: '#FFF5E0',
  text: '#22181C',
  heatSoil: '#F05D23',
  waterRain: '#4A7B9D',
  waterRainLight: '#6FA0C2',
  waterRainSoft: '#E2EFF7',
  waterRainDark: '#2E5670',
  waterRainDarker: '#1F3D52',
  goldYellow: '#D99B26',
  earthBrown: '#8C5A3C',
  primaryLighter: '#8AA15B',
  riskCritical: '#B8292F',
  terracotta: '#9E472A',
  terracottaDark: '#7A331C',
  terracottaDarker: '#592311',
  earthBrownDark: '#633D26',
  regionTop: '#D9733A',
  regionTopHover: '#F08A4B',
  regionAvailable: 'rgba(138, 161, 91, 0.62)',
  regionLocked: '#E4D6BA',
  regionLockedHover: '#D9C7A2',
  regionLockedBorder: '#C7B090',
} as const
