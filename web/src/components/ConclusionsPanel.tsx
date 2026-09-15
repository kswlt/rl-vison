import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useConditions, useSelection } from '../state/store'
import type { EventBehavior } from '../types'

export default function ConclusionsPanel() {
  const teamId = useSelection((s) => s.teamId)
  const conditions = useConditions((s) => s.conditions)
  const [responses, setResponses] = useState<EventBehavior[] | null>(null)
  const [loading, setLoading] = useState(false)

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
                </div>
              ))}
            </div>
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
