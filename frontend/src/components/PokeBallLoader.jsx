import PokeballIcon from './PokeballIcon'

export default function PokeBallLoader({ size = 32, className = '' }) {
  return (
    <div className={`flex items-center justify-center ${className}`} role="img" aria-label="Loading...">
      <PokeballIcon size={size} className="pokeball-loader" style={{ opacity: 0.8 }} />
    </div>
  )
}
