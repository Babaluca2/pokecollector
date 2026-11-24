import { useContext } from 'react'
import SettingsContext from '../contexts/SettingsContext'
import { getPokeball } from '../utils/pokeballs'

// Reads the user's chosen ball; falls back to the classic one outside the settings provider.
export function useSelectedPokeball() {
  const ctx = useContext(SettingsContext)
  return getPokeball(ctx?.settings?.pokeball_style)
}

export default function PokeballIcon({ ball, size = 32, className = '', style }) {
  const selected = useSelectedPokeball()
  const b = ball || selected
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      style={style}
      aria-hidden="true"
    >
      <circle cx="50" cy="50" r="48" fill={b.top} />
      <path d="M 2 50 A 48 48 0 0 0 98 50 Z" fill={b.bottom} />
      {b.marks === 'stripes' && (
        <>
          <path d="M 16 30 L 30 20 L 34 28 L 20 38 Z" fill={b.accent} />
          <path d="M 84 30 L 70 20 L 66 28 L 80 38 Z" fill={b.accent} />
        </>
      )}
      {b.marks === 'dots' && (
        <>
          <circle cx="24" cy="30" r="7" fill={b.accent} />
          <circle cx="76" cy="30" r="7" fill={b.accent} />
        </>
      )}
      <circle cx="50" cy="50" r="48" fill="none" stroke="#222" strokeWidth="3" />
      <line x1="2" y1="50" x2="98" y2="50" stroke={b.band} strokeWidth="6" />
      <circle cx="50" cy="50" r="14" fill={b.button} stroke="#222" strokeWidth="6" />
      <circle cx="50" cy="50" r="6" fill={b.top === '#F5F5F5' ? b.band : b.top} opacity="0.9" />
    </svg>
  )
}
