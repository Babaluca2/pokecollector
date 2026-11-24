// Ball palettes taken from the games. `accent` colours the two side marks drawn on the upper half.
export const POKEBALLS = [
  { id: 'poke', name: 'Poké Ball', top: '#EE1515', bottom: '#F5F5F5', band: '#222222', button: '#F5F5F5' },
  { id: 'great', name: 'Super Ball', top: '#3B6FD4', bottom: '#F5F5F5', band: '#222222', button: '#F5F5F5', accent: '#EE1515', marks: 'stripes' },
  { id: 'ultra', name: 'Hyper Ball', top: '#2B2B2B', bottom: '#F5F5F5', band: '#222222', button: '#F5F5F5', accent: '#F2C230', marks: 'stripes' },
  { id: 'master', name: 'Master Ball', top: '#7B3FA0', bottom: '#F5F5F5', band: '#222222', button: '#F5F5F5', accent: '#E86AA6', marks: 'dots' },
  { id: 'safari', name: 'Safari Ball', top: '#6B8E3A', bottom: '#D9C48C', band: '#3F4A2A', button: '#F5F5F5' },
  { id: 'premier', name: 'Honor Ball', top: '#F5F5F5', bottom: '#F5F5F5', band: '#EE1515', button: '#F5F5F5' },
  { id: 'luxury', name: 'Luxe Ball', top: '#1E1E1E', bottom: '#2A2A2A', band: '#D4A93C', button: '#D4A93C', accent: '#D4A93C', marks: 'stripes' },
  { id: 'heal', name: 'Soin Ball', top: '#F48FB1', bottom: '#F5F5F5', band: '#222222', button: '#F5F5F5', accent: '#EE1515', marks: 'dots' },
  { id: 'timer', name: 'Chrono Ball', top: '#EE1515', bottom: '#F5F5F5', band: '#222222', button: '#F5F5F5', accent: '#222222', marks: 'stripes' },
  { id: 'nest', name: 'Faiblo Ball', top: '#7DB844', bottom: '#F2C230', band: '#222222', button: '#F5F5F5' },
  { id: 'net', name: 'Filet Ball', top: '#3FA796', bottom: '#2A2A2A', band: '#222222', button: '#F5F5F5' },
  { id: 'dive', name: 'Scuba Ball', top: '#2F7FD1', bottom: '#8CC8F0', band: '#222222', button: '#F5F5F5' },
  { id: 'repeat', name: 'Bis Ball', top: '#F2C230', bottom: '#EE5A15', band: '#222222', button: '#F5F5F5' },
  { id: 'quick', name: 'Rapide Ball', top: '#3B8FE0', bottom: '#F2C230', band: '#222222', button: '#F5F5F5' },
  { id: 'dusk', name: 'Sombre Ball', top: '#3D8F3D', bottom: '#222222', band: '#222222', button: '#EE5A15' },
  { id: 'cherish', name: 'Mémoire Ball', top: '#B31217', bottom: '#222222', band: '#F2C230', button: '#F2C230' },
  { id: 'dream', name: 'Rêve Ball', top: '#F5F5F5', bottom: '#F6B3CF', band: '#E86AA6', button: '#F5F5F5' },
  { id: 'love', name: 'Love Ball', top: '#F06292', bottom: '#F5F5F5', band: '#222222', button: '#F5F5F5', accent: '#F5F5F5', marks: 'dots' },
  { id: 'moon', name: 'Lune Ball', top: '#2C3E8C', bottom: '#F5F5F5', band: '#222222', button: '#F2C230' },
  { id: 'friend', name: 'Copain Ball', top: '#4CAF50', bottom: '#F5F5F5', band: '#222222', button: '#F5F5F5', accent: '#F5F5F5', marks: 'dots' },
  { id: 'fast', name: 'Speed Ball', top: '#F2C230', bottom: '#F5F5F5', band: '#222222', button: '#F5F5F5', accent: '#222222', marks: 'stripes' },
  { id: 'heavy', name: 'Masse Ball', top: '#3F6FB5', bottom: '#2A2A2A', band: '#8A8A8A', button: '#F5F5F5' },
  { id: 'level', name: 'Niveau Ball', top: '#EE1515', bottom: '#2A2A2A', band: '#F5F5F5', button: '#F5F5F5' },
  { id: 'sport', name: 'Parc Ball', top: '#E8761C', bottom: '#F5F5F5', band: '#222222', button: '#F5F5F5' },
]

export const DEFAULT_POKEBALL = 'poke'

export function getPokeball(id) {
  return POKEBALLS.find((ball) => ball.id === id) || POKEBALLS[0]
}
