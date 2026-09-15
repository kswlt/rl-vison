import { useConditions, useSelection } from '../state/store'
import { api } from '../api/client'
import { useEffect, useState } from 'react'
import type { Match } from '../types'

const PHASES = [
  { key: '', label: '全场' },
  { key: 'open30', label: '0-30s' },
  { key: 'early30_120', label: '30-120s' },
  { key: 'mid', label: '中期' },
  { key: 'final120', label: '最后120s' },
  { key: 'final90', label: '最后90s' },
  { key: 'final60', label: '最后60s' },
]
const RTYPES = ['', '步兵3', '步兵4', '哨兵', '英雄', '工程', '空中']
const OUTPOST = [
  { key: '', label: '前哨任意' },
  { key: 'full', label: '前哨满血' },
  { key: 'lt75', label: '前哨<75%' },
  { key: 'lt50', label: '前哨<50%' },
  { key: 'lt25', label: '前哨<25%' },
  { key: 'dead', label: '前哨死亡' },
]
const NUMBERS = [
  { key: '', label: '人数任意' },
  { key: 'full', label: '双方满员' },
  { key: 'self_down', label: '己方减员' },
  { key: 'enemy_down', label: '敌方减员' },
  { key: 'adv', label: '人数优势' },
  { key: 'disadv', label: '人数劣势' },
]

export default function FilterBar() {
  const teams = useSelection((s) => s.teams)
  const teamId = useSelection((s) => s.teamId)
  const selectTeam = useSelection((s) => s.selectTeam)
  const conditions = useConditions((s) => s.conditions)
  const setCondition = useConditions((s) => s.setCondition)
  const [allMatches, setAllMatches] = useState<Match[]>([])

  // load the league match list once (for cross-team browsing)
  useEffect(() => {
    api.matches({ limit: 60 }).then(setAllMatches).catch(() => setAllMatches([]))
  }, [])

  return (
    <div className="filterbar">
      <div className="group">
        <label>对手</label>
        <select
          value={teamId}
          onChange={(e) => void selectTeam(e.target.value)}
          style={{ minWidth: 170 }}
        >
          <option value="">全联盟</option>
          {teams.map((t) => (
            <option key={t.team_id} value={t.team_id}>
              {t.school_name}（{t.match_count}场）
            </option>
          ))}
        </select>
      </div>

      <div className="group">
        <label>比赛</label>
        <select
          value={''}
          onChange={(e) => {
            const gid = Number(e.target.value)
            if (gid) void useSelection.getState().selectGame(gid)
          }}
          style={{ minWidth: 200 }}
        >
          <option value="">选一场比赛…</option>
          {useSelection.getState().matches.map((m) => (
            <option key={m.game_id} value={m.game_id}>
              vs {m.opponent} · {m.camp}方{` `}
              {m.won ? '胜' : '负'} · {Math.round(m.duration / 60)}min
            </option>
          ))}
          {allMatches.map((m) => (
            <option key={m.game_id} value={m.game_id}>
              {m.red_school} vs {m.blue_school}
            </option>
          ))}
        </select>
      </div>

      <div className="group">
        <label>兵种</label>
        <select value={conditions.rtype}
          onChange={(e) => setCondition('rtype', e.target.value)}>
          {RTYPES.map((r) => (
            <option key={r} value={r}>{r || '全部兵种'}</option>
          ))}
        </select>
      </div>

      <div className="group">
        <label>阶段</label>
        <select value={conditions.phase}
          onChange={(e) => setCondition('phase', e.target.value)}>
          {PHASES.map((p) => (
            <option key={p.key} value={p.key}>{p.label}</option>
          ))}
        </select>
      </div>

      <div className="group">
        <label>结构</label>
        <select value={conditions.outpost}
          onChange={(e) => setCondition('outpost', e.target.value)}>
          {OUTPOST.map((o) => (
            <option key={o.key} value={o.key}>{o.label}</option>
          ))}
        </select>
      </div>

      <div className="group">
        <label>人数</label>
        <select value={conditions.numbers}
          onChange={(e) => setCondition('numbers', e.target.value)}>
          {NUMBERS.map((n) => (
            <option key={n.key} value={n.key}>{n.label}</option>
          ))}
        </select>
      </div>
    </div>
  )
}
