import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useSelection } from '../state/store'
import type { TeamProfile } from '../types'
import RadarChart from './charts/RadarChart'

export default function OpponentPanel() {
  const teamId = useSelection((s) => s.teamId)
  const matches = useSelection((s) => s.matches)
  const gameId = useSelection((s) => s.gameId)
  const selectGame = useSelection((s) => s.selectGame)
  const [profile, setProfile] = useState<TeamProfile | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!teamId) {
      setProfile(null)
      return
    }
    setLoading(true)
    setError('')
    api.teamProfile(teamId)
      .then(setProfile)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [teamId])

  return (
    <div className="panel">
      <div className="panel-title">
        <span>对手画像</span>
        <span className="dim">{teamId ? '' : '全联盟'}</span>
      </div>
      <div className="panel-body">
        {!teamId && <div className="empty">选择一个对手查看画像</div>}
        {teamId && loading && <div className="empty">计算画像中…</div>}
        {teamId && error && <div className="empty">{error}</div>}
        {profile && (
          <>
            <RadarChart metrics={profile.metrics} />
            <div className="metrics" style={{ marginTop: 10 }}>
              {profile.metrics.map((m) => (
                <div className="metric-row" key={m.key}>
                  <div>
                    <div className="m-label">{m.label}</div>
                    <div className="vs">
                      <span>联盟 {m.league_avg}</span>
                      {m.top_avg > 0 && <span>Top {m.top_avg}</span>}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div className="m-value">
                      {m.value}{m.unit}
                    </div>
                    <div className="m-sub">n={m.n_matches}场</div>
                  </div>
                </div>
              ))}
              {profile.metrics.some((m) => !m.reliable) && (
                <div className="insufficient">⚠ 样本不足，结论可靠性低</div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="panel-title" style={{ borderTop: '1px solid var(--border)' }}>
        <span>历史比赛</span>
        <span className="dim">{matches.length}场</span>
      </div>
      <div className="panel-body" style={{ paddingTop: 6 }}>
        {matches.length === 0 && <div className="empty">暂无比赛</div>}
        <div className="list">
          {matches.map((m) => (
            <div key={m.game_id}
              className={`list-item ${m.game_id === gameId ? 'active' : ''}`}
              onClick={() => void selectGame(m.game_id)}>
              <div className="row1">
                <span>
                  <span className={`camp-tag ${m.camp === '红' ? 'red' : 'blue'}`}>
                    {m.camp}
                  </span>
                  {' '}vs {m.opponent}
                </span>
                {m.won
                  ? <span className="win-tag">胜</span>
                  : <span className="lose-tag">负</span>}
              </div>
              <div className="row2">
                {m.region} · {m.started_at?.slice(0, 10) ?? ''} · {Math.round(m.duration / 60)}min
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
