import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useConditions, useSelection, useTimeline } from '../state/store'
import type { EventBehavior } from '../types'

export default function ConclusionsPanel() {
  const teamId = useSelection((s) => s.teamId)
  const conditions = useConditions((s) => s.conditions)
  const selectGame = useSelection((s) => s.selectGame)
  const seek = useTimeline((s) => s.seek)
  const [responses, setResponses] = useState<EventBehavior[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [openCase, setOpenCase] = useState<string | null>(null)

  useEffect(() => {
    if (!teamId) {
      setResponses(null)
      return
    }
    setLoading(true)
    api.eventResponse(teamId, conditions.rtype, 15)
      .then((r) => setResponses(r.filter((x) => x.n >= 1)))
      .catch(() => setResponses([]))
      .finally(() => setLoading(false))
  }, [teamId, conditions.rtype])

  const playCase = async (gameId: number, t: number) => {
    await selectGame(gameId)
    seek(Math.max(0, t - 5))
  }

  return (
    <div className="panel">
      <div className="panel-title">
        <span>战术结论</span>
        <span className="dim">事件 → 行为</span>
      </div>
      <div className="panel-body">
        {!teamId && <div className="empty">选择对手后显示事件响应分析</div>}
        {teamId && loading && <div className="empty">统计中…</div>}
        {teamId && responses?.length === 0 && (
          <div className="empty">暂无足够样本的事件响应</div>
        )}
        {responses?.map((r) => (
          <div key={r.event} style={{ marginBottom: 14 }}>
            <div style={{ fontWeight: 600, fontSize: 12.5 }}>
              {EVENT_LABEL[r.event] ?? r.event}
            </div>
            <div className="sample-line">未来 {r.horizon_s}s · n={r.n} · {r.n_matches} 场比赛</div>
            <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {Object.entries(r.behaviors).slice(0, 4).map(([b, pct]) => (
                <div key={b} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    onClick={() =>
                      setOpenCase((prev) => (prev === r.event ? null : r.event))
                    }
                    style={{
                      background: 'transparent', border: 'none', color: 'inherit',
                      cursor: 'pointer', padding: 0, fontFamily: 'inherit',
                      display: 'flex', alignItems: 'center', gap: 8, flex: 1,
                      minWidth: 0, textAlign: 'left',
                    }}
                    title="查看真实案例">
                    <span style={{ minWidth: 34, fontSize: 12, color: 'var(--text-dim)' }}>
                      {b}
                    </span>
                    <div style={{
                      flex: 1, height: 8, borderRadius: 4,
                      background: 'var(--panel-alt)',
                    }}>
                      <div style={{
                        width: `${pct}%`, height: 8, borderRadius: 4,
                        background: pct >= 50 ? 'var(--ai)' : 'var(--border-strong)',
                        transition: 'width 500ms cubic-bezier(.4,0,.2,1)',
                      }} />
                    </div>
                    <span className="mono" style={{ minWidth: 44, fontSize: 12 }}>
                      {pct}%
                    </span>
                  </button>
                </div>
              ))}
            </div>
            {openCase === r.event && r.cases.length > 0 && (
              <div style={{
                marginTop: 6, padding: 6, background: 'var(--panel-alt)',
                borderRadius: 4, fontSize: 11,
              }}>
                <div className="dim" style={{ marginBottom: 4 }}>
                  真实案例 {r.cases.length} 个 —— 点击跳到该场该时刻
                </div>
                {r.cases.slice(0, 6).map((c, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between',
                    padding: '2px 0' }}>
                    <span>
                      #{i + 1} vs {c.opponent} · {c.rtype}#{c.robot_id} · {c.detail}
                    </span>
                    <button className="btn" style={{ padding: '0 8px' }}
                      onClick={() => void playCase(c.game_id, c.t)}>
                      播放
                    </button>
                  </div>
                ))}
              </div>
            )}
            {!r.n_matches && <div className="insufficient">样本不足</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

const EVENT_LABEL: Record<string, string> = {
  outpost_lt75: '前哨 HP < 75%',
  outpost_lt50: '前哨 HP < 50%',
  outpost_lt25: '前哨 HP < 25%',
  outpost_destroyed: '前哨摧毁',
  base_hit: '基地受击',
  own_robot_down: '己方机器人阵亡',
  enemy_robot_down: '敌方机器人阵亡',
  numbers_advantage: '人数优势',
  numbers_disadvantage: '人数劣势',
}
