import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useConditions, useSelection } from '../state/store'
import type { Formation, Heatmap } from '../types'
import * as echarts from 'echarts'
import { useRef } from 'react'
import { theme } from '../theme'

const TABS = [
  { key: 'heat', label: '条件统计' },
  { key: 'formation', label: '阵型' },
  { key: 'matchup', label: '对手比较' },
  { key: 'ai', label: 'AI分析' },
  { key: 'evidence', label: '历史证据' },
] as const

export default function TabsPanel() {
  const [tab, setTab] = useState<string>('heat')
  return (
    <div style={{
      background: 'var(--bg-elev)', borderTop: '1px solid var(--border)',
      minHeight: 210, maxHeight: 320, display: 'flex', flexDirection: 'column',
    }}>
      <div className="tabs">
        {TABS.map((t) => (
          <div key={t.key} className={`tab ${tab === t.key ? 'active' : ''}`}
            onClick={() => setTab(t.key)}>
            {t.label}
          </div>
        ))}
      </div>
      <div className="tab-body" style={{ flex: 1 }}>
        {tab === 'heat' && <HeatTab />}
        {tab === 'formation' && <FormationTab />}
        {tab === 'matchup' && <div className="empty">Matchup Analysis（M6 实现）</div>}
        {tab === 'ai' && <div className="empty">AI 分析：RL 集成在 M8 接入</div>}
        {tab === 'evidence' && <div className="empty">历史证据：录像集成在 M7 接入</div>}
      </div>
    </div>
  )
}

function HeatTab() {
  const conditions = useConditions((s) => s.conditions)
  const teamId = useSelection((s) => s.teamId)
  const [heat, setHeat] = useState<Heatmap | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!teamId) {
      setHeat(null)
      return
    }
    setLoading(true)
    api.heatmap({ ...conditions, team: teamId })
      .then(setHeat)
      .catch(() => setHeat(null))
      .finally(() => setLoading(false))
  }, [teamId, conditions])

  return (
    <div>
      {!teamId && <div className="empty">选择对手后显示条件热力统计</div>}
      {teamId && loading && <div className="empty">聚合中…（首次较慢，后续走缓存）</div>}
      {heat && (
        <>
          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 6 }}>
            条件：{heat.phase || '全场'} · {heat.rtype || '全部兵种'}
            {' '}· 样本 {heat.n} 个机器人秒 · {heat.n_matches} 场
            {heat.note && <span style={{ color: 'var(--warn)' }}>（{heat.note}）</span>}
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
            gap: 4, maxHeight: 200, overflowY: 'auto',
          }}>
            {heat.cells.slice(0, 80).map((c) => (
              <div key={`${c.x}-${c.y}`} className="metric-row" style={{ fontSize: 11 }}>
                <span className="m-label">格({c.x},{c.y})</span>
                <span className="m-value">{Math.round(c.count)}</span>
              </div>
            ))}
            {heat.cells.length === 0 && <div className="empty">该条件下无样本</div>}
          </div>
        </>
      )}
    </div>
  )
}

function FormationTab() {
  const gameId = useSelection((s) => s.gameId)
  const [form, setForm] = useState<Formation | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (gameId == null) {
      setForm(null)
      return
    }
    api.formation(gameId, '红', 2).then(setForm).catch(() => setForm(null))
  }, [gameId])

  useEffect(() => {
    if (!ref.current || !form || form.points.length < 2) return
    const chart = echarts.init(ref.current)
    const pts = form.points
    const xs = pts.map((p) => p.t)
    chart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { textStyle: { color: theme.textDim, fontSize: 10 }, top: 0 },
      grid: { left: 40, right: 12, top: 26, bottom: 22 },
      xAxis: {
        type: 'category', data: xs.map((t) => `${Math.round(t)}s`),
        axisLabel: { color: theme.textFaint, fontSize: 10 },
        axisLine: { lineStyle: { color: theme.borderStrong } },
      },
      yAxis: {
        type: 'value', axisLabel: { color: theme.textFaint, fontSize: 10 },
        splitLine: { lineStyle: { color: theme.border } },
      },
      series: [
        { name: '阵型宽度(m)', type: 'line', showSymbol: false,
          data: pts.map((p) => p.width), lineStyle: { color: theme.ai, width: 1.5 },
          itemStyle: { color: theme.ai } },
        { name: '阵型纵深(m)', type: 'line', showSymbol: false,
          data: pts.map((p) => p.depth), lineStyle: { color: theme.red, width: 1.5 },
          itemStyle: { color: theme.red } },
        { name: '集中程度', type: 'line', showSymbol: false,
          data: pts.map((p) => p.concentration * 15),
          lineStyle: { color: theme.textFaint, width: 1, type: 'dashed' },
          itemStyle: { color: theme.textFaint } },
      ],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [form])

  if (!gameId) return <div className="empty">选择比赛后查看阵型时间序列</div>
  if (!form) return <div className="empty">加载阵型数据…</div>
  if (form.points.length < 2) return <div className="empty">暂无阵型数据</div>
  return <div ref={ref} style={{ height: 190, width: '100%' }} />
}
