/** TypeScript mirror of the backend Pydantic schemas (rm_rl/tactical/schemas.py). */

export interface Team {
  team_id: string
  school_name: string
  team_name?: string | null
  aliases: string[]
  match_count: number
  win_rate: number
}

export interface TeamProfileMetric {
  key: string
  label: string
  value: number
  league_avg: number
  top_avg: number
  n: number
  n_matches: number
  unit: string
  reliable: boolean
}

export interface TeamProfile {
  team_id: string
  school_name: string
  metrics: TeamProfileMetric[]
}

export interface TeamMatch {
  game_id: number
  region: string
  round_no: number
  opponent: string
  camp: string
  winner: string
  duration: number
  started_at: string
  won: boolean
}

export interface Match {
  game_id: number
  region: string
  match_no: number
  round_no: number
  red_school: string
  blue_school: string
  winner: string
  duration: number
  started_at: string
  red_team_id: string
  blue_team_id: string
}

export interface RobotState {
  robot_id: number
  rtype: string
  camp: string
  school: string
  x: number
  y: number
  z: number
  hp: number
  maxhp: number
  yaw: number
  yaw_ok: boolean
  alive: boolean
  known: boolean
  ammo17: number
  heat17: number
  vuln: boolean
  power: number
}

export interface MatchState {
  game_id: number
  t: number
  duration: number
  robots: RobotState[]
  buildings: RobotState[]
}

export interface TimelinePoint {
  t: number
  events: string[]
}

export interface MatchTimeline {
  game_id: number
  duration: number
  points: TimelinePoint[]
}

export interface EventItem {
  t: number
  etype: string
  robot_id: number
  rtype: string
  camp: string
  school: string
  target_id?: number | null
  target_type: string
  category: string
  value?: number | null
  note: string
}

export interface HeatmapCell {
  x: number
  y: number
  count: number
  density: number
}

export interface Heatmap {
  team_id: string
  rtype: string
  phase: string
  nx: number
  ny: number
  cell_m: number
  cells: HeatmapCell[]
  n: number
  n_matches: number
  reliable: boolean
  note: string
}

export interface FlowCell {
  x: number
  y: number
  mean_dx: number
  mean_dy: number
  speed: number
  n: number
  enter_dir: number
  leave_dir: number
  stay_time: number
  common_next?: number[] | null
}

export interface Flow {
  team_id: string
  rtype: string
  phase: string
  nx: number
  ny: number
  cell_m: number
  cells: FlowCell[]
  n: number
  n_matches: number
}

export interface FormationPoint {
  t: number
  centroid_x: number
  centroid_y: number
  width: number
  depth: number
  spacing: number
  front_robot: string
  back_robot: string
  area: number
  concentration: number
}

export interface Formation {
  game_id: number
  camp: string
  points: FormationPoint[]
}

export interface BehaviorCase {
  game_id: number
  t: number
  opponent: string
  bvid: string
  video_url: string
  video_time?: number | null
  aligned: boolean
  robot_id: number
  rtype: string
  detail: string
}

export interface EventBehavior {
  event: string
  team_id: string
  horizon_s: number
  behaviors: Record<string, number>
  n: number
  n_matches: number
  cases: BehaviorCase[]
}

export interface VideoAnchor {
  id: number
  match_video_id: number
  game_time: number
  video_time: number
  confidence: number
}

export interface Video {
  id: number
  game_id: number
  platform: string
  bvid: string
  url: string
  title: string
  offset?: number | null
  alignment_status: string
  anchors: VideoAnchor[]
}

export interface Inference {
  game_id: number
  t: number
  algo: string
  goal_dx: number
  goal_dy: number
  fire: boolean
  p_fire: number
  target?: number | null
  target_label: string
  target_conf: number
  target_probs: number[]
  human: Record<string, unknown>
  agree: Record<string, unknown>
}

/** Global tactical conditions used by the analysis panels. */
export interface TacticalConditions {
  team: string
  rtype: string
  phase: string
  outpost: string
  numbers: string
  robotHp: string
  robotAmmo: string
  baseHit: boolean
}

export const DEFAULT_CONDITIONS: TacticalConditions = {
  team: '',
  rtype: '',
  phase: '',
  outpost: '',
  numbers: '',
  robotHp: '',
  robotAmmo: '',
  baseHit: false,
}
