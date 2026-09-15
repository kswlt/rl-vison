/**
 * Design tokens — F1 telemetry × esports analytics × military situational map.
 * Dark charcoal base, low-saturation field, RM red/blue semantics, cyan for
 * AI recommendations, orange/red for danger. No neon, no flashing.
 */
export const theme = {
  bg: '#0d1117',
  bgElevated: '#14181f',
  panel: '#161b22',
  panelAlt: '#1c2128',
  border: '#21262d',
  borderStrong: '#30363d',
  text: '#e6edf3',
  textDim: '#7d8590',
  textFaint: '#57606a',

  red: '#ff5b3d',
  blue: '#4d9dff',
  enemyRed: '#ff5b3d',
  allyBlue: '#4d9dff',
  danger: '#ff8f4d',
  dangerStrong: '#f85149',
  ai: '#3fc9c9',
  aiAlt: '#56d4dd',
  good: '#4dd97e',
  warn: '#f7d154',

  grid: '#1b2129',
  fieldLine: '#2a323d',
  fieldFill: '#11161d',
  heatLow: '#1f2a6e',
  heatMid: '#3b6fd4',
  heatHigh: '#f7d154',
  heatPeak: '#ff5b3d',

  font: '"Inter", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
  mono: '"JetBrains Mono", "SFMono-Regular", Consolas, monospace',

  radius: 6,
  radiusSm: 4,
  transition: '200ms cubic-bezier(.4,0,.2,1)',
  transitionHeat: '500ms cubic-bezier(.4,0,.2,1)',
} as const

export type Theme = typeof theme
