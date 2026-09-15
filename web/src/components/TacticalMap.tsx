import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { useSelection, useTimeline, useLayers, LAYER_DEFS } from '../state/store'
import type { MatchState, RobotState } from '../types'
import { theme } from '../theme'

const W = 560  // svg width
const H = 300  // svg height (28x15m at 20px/m)
const M2PX = 20

const TYPE_LABEL: Record<string, string> = {
  英雄: 'H', 工程: 'E', 步兵3: 'I3', 步兵4: 'I4', 空中: 'A', 哨兵: 'S',
  基地: 'B', 前哨站: 'O',
}

function Robot({ r }: { r: RobotState }) {
  const x = r.x * M2PX
  const y = r.y * M2PX
  const color = r.camp === '红' ? theme.red : theme.blue
  const isBuild = r.rtype === '基地' || r.rtype === '前哨站'
  const rOut = isBuild ? 16 : 9
  const hpFrac = r.maxhp > 0 ? Math.max(0, Math.min(1, r.hp / r.maxhp)) : 0
  if (!r.known || !r.alive) {
    return r.known ? (
      <g opacity={0.25} transform={`translate(${x},${y})`}>
        <circle r={rOut} fill={color} stroke="none" />
        <text textAnchor="middle" dy="4" fontSize={10} fill="#0d1117"
          fontFamily="monospace">{TYPE_LABEL[r.rtype] ?? r.robot_id}</text>
      </g>
    ) : null
  }
  return (
    <g transform={`translate(${x},${y})`}>
      {/* heading */}
      {r.yaw_ok && (
        <line x1={0} y1={0}
          x2={Math.cos((r.yaw * Math.PI) / 180) * rOut * 1.5}
          y2={Math.sin((r.yaw * Math.PI) / 180) * rOut * 1.5}
          stroke={color} strokeWidth={2} opacity={0.9} />
      )}
      {/* hp ring */}
      <circle r={rOut + 3} fill="none" stroke="#21262d" strokeWidth={3} />
      <circle r={rOut + 3} fill="none"
        stroke={hpFrac > 0.5 ? theme.good : hpFrac > 0.25 ? theme.warn : theme.dangerStrong}
        strokeWidth={3}
        strokeDasharray={`${hpFrac * 2 * Math.PI * (rOut + 3)} ${2 * Math.PI * (rOut + 3)}`}
        transform="rotate(-90)" />
      <circle r={rOut} fill={color} opacity={0.88} />
      <text textAnchor="middle" dy="4" fontSize={10} fill="#0d1117"
        fontFamily="monospace" fontWeight={700}>
        {TYPE_LABEL[r.rtype] ?? r.robot_id}
      </text>
    </g>
  )
}

export default function TacticalMap() {
  const gameId = useSelection((s) => s.gameId)
  const time = useTimeline((s) => s.time)
  const layers = useLayers((s) => s.layers)
  const toggleLayer = useLayers((s) => s.toggleLayer)
  const [state, setState] = useState<MatchState | null>(null)

  useEffect(() => {
    if (gameId == null) {
      setState(null)
      return
    }
    let cancelled = false
    api.state(gameId, Math.round(time)).then((s) => {
      if (!cancelled) setState(s)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [gameId, time])

  const grid = useMemo(() => {
    const lines = []
    for (let x = 1; x < 28; x++) {
      lines.push(<line key={`v${x}`} x1={x * M2PX} y1={0} x2={x * M2PX} y2={H}
        stroke={theme.fieldLine} strokeWidth={0.5} />)
    }
    for (let y = 1; y < 15; y++) {
      lines.push(<line key={`h${y}`} x1={0} y1={y * M2PX} x2={W} y2={y * M2PX}
        stroke={theme.fieldLine} strokeWidth={0.5} />)
    }
    return lines
  }, [])

  const robots = state?.robots ?? []
  const buildings = state?.buildings ?? []

  return (
    <div className="map-stage">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%"
        preserveAspectRatio="xMidYMid meet" style={{ background: theme.fieldFill }}>
        {/* half-court tints */}
        <rect x={0} y={0} width={W / 2} height={H} fill="#ff5b3d08" />
        <rect x={W / 2} y={0} width={W / 2} height={H} fill="#4d9dff08" />
        {/* centre line */}
        <line x1={W / 2} y1={0} x2={W / 2} y2={H} stroke={theme.fieldLine}
          strokeWidth={1.5} strokeDasharray="6 4" />
        {grid}
        {/* building zones */}
        <rect x={10} y={10} width={70} height={44} rx={4} fill="none"
          stroke={theme.red} strokeWidth={1} opacity={0.35} />
        <rect x={W - 80} y={H - 54} width={70} height={44} rx={4} fill="none"
          stroke={theme.blue} strokeWidth={1} opacity={0.35} />

        {layers.robots && buildings.map((b) => <Robot key={b.robot_id} r={b} />)}
        {layers.robots && robots.map((r) => <Robot key={r.robot_id} r={r} />)}

        {!state && (
          <text x={W / 2} y={H / 2} textAnchor="middle" fill={theme.textFaint}
            fontSize={13}>
            {gameId == null ? '请选择一场比赛' : '加载中…'}
          </text>
        )}
      </svg>

      {/* layers control */}
      <div style={{
        position: 'absolute', top: 10, right: 10,
        background: 'rgba(22,27,34,.92)', border: `1px solid ${theme.borderStrong}`,
        borderRadius: 6, padding: 8, fontSize: 11, minWidth: 150,
        color: theme.textDim,
      }}>
        <div style={{ fontWeight: 600, marginBottom: 4, color: theme.text }}>
          Layers
        </div>
        {LAYER_DEFS.map((l) => (
          <label key={l.key} style={{ display: 'flex', gap: 6, padding: '1px 0',
            cursor: 'pointer', alignItems: 'center' }}>
            <input type="checkbox" checked={!!layers[l.key]}
              onChange={() => toggleLayer(l.key)}
              style={{ accentColor: theme.ai }} />
            {l.label}
          </label>
        ))}
      </div>

      <div style={{
        position: 'absolute', bottom: 8, left: 12, fontSize: 11,
        color: theme.textFaint,
      }}>
        t={time.toFixed(0)}s · 场地 28×15 m · 1 Hz 裁判数据（前端插值显示）
      </div>
    </div>
  )
}
