/**
 * API client — thin typed wrapper over the FastAPI backend.
 * Uses relative /api URLs; Vite proxies to the backend in dev, FastAPI serves
 * the same origin in production.
 */
import type {
  DisagreementOut, EventBehavior, EventItem, Flow, Formation, Heatmap,
  Inference, Match, MatchState, MatchStates, MatchTimeline, Matchup, Team,
  TeamMatch, TeamProfile, Video, VideoAnchor, VideoLibrary,
  TacticalConditions,
} from '../types'

const BASE = '/api'

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const qs = new URLSearchParams()
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') {
        qs.set(k, String(v))
      }
    }
  }
  const q = qs.toString()
  const res = await fetch(`${BASE}${path}${q ? `?${q}` : ''}`)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body?.detail ?? detail
    } catch { /* keep statusText */ }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const b = await res.json()
      detail = b?.detail ?? detail
    } catch { /* keep statusText */ }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => get<{ status: string; matches: number }>('/health'),
  teams: () => get<Team[]>('/teams'),
  team: (id: string) => get<Team>(`/teams/${encodeURIComponent(id)}`),
  teamProfile: (id: string) => get<TeamProfile>(`/teams/${encodeURIComponent(id)}/profile`),
  teamMatches: (id: string) => get<TeamMatch[]>(`/teams/${encodeURIComponent(id)}/matches`),
  matches: (params?: { team?: string; region?: string; limit?: number }) =>
    get<Match[]>('/matches', params),
  match: (id: number) => get<Match>(`/matches/${id}`),
  timeline: (id: number) => get<MatchTimeline>(`/matches/${id}/timeline`),
  state: (id: number, t: number) => get<MatchState>(`/matches/${id}/state`, { t }),
  states: (id: number, step = 1) => get<MatchStates>(`/matches/${id}/states`, { step }),
  events: (id: number, etype?: string, limit?: number) =>
    get<EventItem[]>(`/matches/${id}/events`, { etype, limit }),

  heatmap: (c: TacticalConditions, extra?: Record<string, unknown>) =>
    get<Heatmap>('/analytics/heatmap', {
      team: c.team, rtype: c.rtype, phase: c.phase, outpost: c.outpost,
      numbers: c.numbers, robot_hp: c.robotHp, robot_ammo: c.robotAmmo,
      base_hit: c.baseHit || undefined, ...extra,
    }),
  flow: (c: TacticalConditions, extra?: Record<string, unknown>) =>
    get<Flow>('/analytics/flow', {
      team: c.team, rtype: c.rtype, phase: c.phase, outpost: c.outpost,
      numbers: c.numbers, ...extra,
    }),
  formation: (gameId: number, camp: string, step = 1) =>
    get<Formation>('/analytics/formation', { game_id: gameId, camp, step }),
  eventResponse: (team: string, rtype = '', horizon = 15, kind = '') =>
    get<EventBehavior[]>('/analytics/event-response',
      { team, rtype, horizon, kind }),
  matchup: (teamA: string, teamB: string) =>
    get<Matchup>('/analytics/matchup', { team_a: teamA, team_b: teamB }),

  videos: (gameId: number) => get<Video[]>(`/videos/${gameId}`),
  addVideo: (v: { game_id: number; platform?: string; bvid: string; url: string; title: string; offset?: number | null }) =>
    post<Video>('/videos', v),
  addAnchor: (videoId: number, a: { game_time: number; video_time: number; confidence?: number }) =>
    post<VideoAnchor>(`/videos/${videoId}/anchors`, a),
  mapToGame: (videoId: number, videoTime: number) =>
    get<{ game_time: number | null }>(`/videos/${videoId}/map`, { video_time: videoTime }),
  mapToVideo: (videoId: number, gameTime: number) =>
    get<{ video_time: number | null }>(`/videos/${videoId}/inverse`, { game_time: gameTime }),

  videoLibrary: () => get<VideoLibrary[]>('/videos/library'),
  videoLibraryAdd: (v: { platform?: string; bvid: string; url: string; title: string; note?: string }) =>
    post<VideoLibrary>('/videos/library', v),
  videoLibraryAssociate: (libId: number, gameId: number) =>
    post<Video>(`/videos/library/${libId}/associate?game_id=${gameId}`, {}),

  inference: (body: { game_id: number; t: number; camp?: string; rtype?: string; algo?: string }) =>
    post<Inference>('/inference', body),
  disagreements: (params: { game_id: number; algo?: string; rtype?: string; top_k?: number; step?: number }) =>
    post<DisagreementOut>(`/inference/disagreements?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])).toString()}`, {}),
}
