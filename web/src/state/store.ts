/**
 * Global store — one source of truth for the platform's selection state and
 * the *global tactical time* that every component (map, charts, timeline,
 * video) shares.
 */
import { create } from 'zustand'
import type { TacticalConditions } from '../types'

export interface TimelineState {
  time: number            // global tactical time (seconds from game start)
  playing: boolean
  speed: number           // 0.5 | 1 | 2 | 4
  duration: number
  setTime: (t: number) => void
  play: () => void
  pause: () => void
  toggle: () => void
  setSpeed: (s: number) => void
  setDuration: (d: number) => void
  step: (dt: number) => void
  seek: (t: number) => void
}

export interface SelectionState {
  teams: import('../types').Team[]
  teamId: string                 // canonical team id ('' = league-wide)
  matches: import('../types').TeamMatch[]
  gameId: number | null
  loadingTeams: boolean
  loadingMatches: boolean
  loadTeams: () => Promise<void>
  selectTeam: (id: string) => Promise<void>
  selectGame: (id: number | null) => Promise<void>
}

export interface ConditionsState {
  conditions: TacticalConditions
  setCondition: <K extends keyof TacticalConditions>(
    key: K, value: TacticalConditions[K]) => void
  setConditions: (c: Partial<TacticalConditions>) => void
}

export interface LayersState {
  layers: Record<string, boolean>
  toggleLayer: (k: string) => void
  setLayer: (k: string, v: boolean) => void
}

export const LAYER_DEFS: { key: string; label: string; defaultOn: boolean }[] = [
  { key: 'robots', label: '机器人', defaultOn: true },
  { key: 'trail10', label: '最近10秒轨迹', defaultOn: true },
  { key: 'trailFull', label: '完整轨迹', defaultOn: false },
  { key: 'heatmap', label: '占位热力图', defaultOn: false },
  { key: 'condHeat', label: '条件热力图', defaultOn: false },
  { key: 'flow', label: '运动流场', defaultOn: false },
  { key: 'fire', label: '发弹热点', defaultOn: false },
  { key: 'hit', label: '受击热点', defaultOn: false },
  { key: 'engage', label: '交火区域', defaultOn: false },
  { key: 'formation', label: '阵型', defaultOn: true },
  { key: 'routes', label: '历史典型路线', defaultOn: false },
  { key: 'rl', label: 'RL建议', defaultOn: true },
  { key: 'human', label: '真人实际动作', defaultOn: true },
]

export const useTimeline = create<TimelineState>((set, get) => ({
  time: 0,
  playing: false,
  speed: 1,
  duration: 0,
  setTime: (t) => set({ time: Math.max(0, Math.min(get().duration, t)) }),
  play: () => set({ playing: true }),
  pause: () => set({ playing: false }),
  toggle: () => set({ playing: !get().playing }),
  setSpeed: (s) => set({ speed: s }),
  setDuration: (d) => set({ duration: d }),
  step: (dt) => {
    const { time, duration } = get()
    const nt = Math.min(duration, Math.max(0, time + dt))
    set({ time: nt })
    if (nt >= duration) set({ playing: false })
  },
  seek: (t) => set({ time: Math.max(0, Math.min(get().duration, t)) }),
}))

export const useSelection = create<SelectionState>((set) => ({
  teams: [],
  teamId: '',
  matches: [],
  gameId: null,
  loadingTeams: false,
  loadingMatches: false,
  loadTeams: async () => {
    set({ loadingTeams: true })
    try {
      const { api } = await import('../api/client')
      const teams = await api.teams()
      set({ teams, loadingTeams: false })
    } catch (e) {
      set({ loadingTeams: false })
      console.error(e)
    }
  },
  selectTeam: async (id) => {
    const { api } = await import('../api/client')
    set({ teamId: id, loadingMatches: true, gameId: null, matches: [] })
    try {
      const matches = await api.teamMatches(id)
      set({ matches, loadingMatches: false })
      if (matches.length) {
        const gameId = matches[0].game_id
        set({ gameId })
        const tl = await api.timeline(gameId)
        useTimeline.getState().setDuration(tl.duration)
      }
    } catch (e) {
      set({ loadingMatches: false })
      console.error(e)
    }
  },
  selectGame: async (id) => {
    set({ gameId: id })
    if (id == null) return
    try {
      const { api } = await import('../api/client')
      const tl = await api.timeline(id)
      useTimeline.getState().setDuration(tl.duration)
      useTimeline.getState().seek(0)
    } catch (e) {
      console.error(e)
    }
  },
}))

export const useConditions = create<ConditionsState>((set) => ({
  conditions: { team: '', rtype: '', phase: '', outpost: '', numbers: '', robotHp: '', robotAmmo: '', baseHit: false } as TacticalConditions,
  setCondition: (key, value) =>
    set((s) => ({ conditions: { ...s.conditions, [key]: value } })),
  setConditions: (c) =>
    set((s) => ({ conditions: { ...s.conditions, ...c } })),
}))

export const useLayers = create<LayersState>((set) => ({
  layers: Object.fromEntries(LAYER_DEFS.map((l) => [l.key, l.defaultOn])),
  toggleLayer: (k) =>
    set((s) => ({ layers: { ...s.layers, [k]: !s.layers[k] } })),
  setLayer: (k, v) => set((s) => ({ layers: { ...s.layers, [k]: v } })),
}))
