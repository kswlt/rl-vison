import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useConditions, useLayers, useMatchup, useSelection } from '../state/store'
import type { Formation, Heatmap, Matchup } from '../types'
import * as echarts from 'echarts'
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
        {tab === 'matchup' && <MatchupTab />}
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

function MatchupTab() {
  const teams = useSelection((s) => s.teams)
  const teamId = useSelection((s) => s.teamId)
  const matchupSel = useMatchup()
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [data, setData] = useState<Matchup | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // default: current team vs its most common league rival later; for now
    // default team A = selected team, team B = first other team
    if (teamId && !a) setA(teamId)
  }, [teamId, a])

  const run = () => {
    if (!a || !b || a === b) {
      setError('请选择两支不同队伍')
      return
    }
    setError('')
    setLoading(true)
    setData(null)
    api.matchup(a, b).then((m) => {
      setData(m)
      matchupSel.setMatchup(m.team_a, m.team_b)
      // make sure the routes layer is on so the map shows the overlay
      useLayers.getState().setLayer('routes', true)
    }).catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!chartRef.current || !data || data.first_contact.times.length < 2) return
    const chart = echarts.init(chartRef.current)
    chart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 12, top: 16, bottom: 22 },
      xAxis: {
        type: 'category', name: '首次交火时间(s)',
        data: data.first_contact.times.map((t) => Math.round(t)),
        axisLabel: { color: theme.textFaint, fontSize: 10 },
        axisLine: { lineStyle: { color: theme.borderStrong } },
        nameTextStyle: { color: theme.textFaint, fontSize: 10 },
      },
      yAxis: {
        type: 'value', name: '次数',
        axisLabel: { color: theme.textFaint, fontSize: 10 },
        splitLine: { lineStyle: { color: theme.border } },
        nameTextStyle: { color: theme.textFaint, fontSize: 10 },
      },
      series: [{
        type: 'bar', data: data.first_contact.times.map(() => 1),
        itemStyle: { color: theme.warn },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data])

  const MiniHeat = ({ cells, color, label, max }: {
    cells: { x: number; y: number; count: number }[]; color: string;
    label: string; max: number
  }) => (
    <div>
      <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>{label}</div>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(28, 1fr)', gap: 1,
        width: '100%', aspectRatio: '28/15',
      }}>
        {Array.from({ length: 28 * 15 }, (_, i) => {
          const x = i % 28
          const y = Math.floor(i / 28)
          const c = cells.find((q) => q.x === x && q.y === y)
          if (!c) return <div key={i} style={{ background: '#161b22' }} />
          const alpha = 0.08 + 0.6 * Math.min(1, c.count / max)
          return <div key={i} style={{ background: color, opacity: alpha }} />
        })}
      </div>
    </div>
  )

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16 }}>
      <div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div>
            <label className="dim" style={{ fontSize: 12 }}>我方 / A 队</label>
            <select value={a} onChange={(e) => setA(e.target.value)}
              style={{ width: '100%', marginTop: 2 }}>
              <option value="">选择队伍…</option>
              {teams.map((t) => <option key={t.team_id} value={t.team_id}>
                {t.school_name}</option>)}
            </select>
          </div>
          <div>
            <label className="dim" style={{ fontSize: 12 }}>对方 / B 队</label>
            <select value={b} onChange={(e) => setB(e.target.value)}
              style={{ width: '100%', marginTop: 2 }}>
              <option value="">选择队伍…</option>
              {teams.map((t) => <option key={t.team_id} value={t.team_id}>
                {t.school_name}</option>)}
            </select>
          </div>
          <button className="btn primary" onClick={run} disabled={loading}>
            {loading ? '分析中…' : '分析对阵'}
          </button>
          {error && <div className="empty">{error}</div>}
          <div className="dim" style={{ fontSize: 11 }}>
            蓝色 = A 队历史位置 · 红色 = B 队历史位置 · 橙色 = 争夺区 ·
            黄色圆点 = 首次交火位置。地图「历史典型路线」图层显示叠加。
          </div>
        </div>
      </div>
      <div>
        {!data && !loading && <div className="empty">选择两队后分析历史对阵</div>}
        {data && (
          <>
            <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
              <MiniHeat cells={data.a_heat} color="#4d9dff"
                label={`${data.team_a} 典型位置（${data.a_heat.length} 格）`}
                max={Math.max(1, ...data.a_heat.map((c) => c.count))} />
              <MiniHeat cells={data.b_heat} color="#ff5b3d"
                label={`${data.team_b} 典型位置（${data.b_heat.length} 格）`}
                max={Math.max(1, ...data.b_heat.map((c) => c.count))} />
            </div>
            <div className="sample-line">
              共同比赛 {data.n_matches} 场 · 首次交火 {data.first_contact.n} 次 ·
              平均 {data.first_contact.mean_t ?? '—'}s ·
              争夺区 {data.overlap.length} 格 · {data.note}
            </div>
            <div ref={chartRef} style={{ height: 120, width: '100%', marginTop: 6 }} />
          </>
        )}
      </div>
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
        { name: '平均间距(m)', type: 'line', showSymbol: false,
          data: pts.map((p) => p.spacing), lineStyle: { color: theme.blue, width: 1.2 },
          itemStyle: { color: theme.blue } },
        { name: '集中程度(x15)', type: 'line', showSymbol: false,
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
