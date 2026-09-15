import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useAI, useConditions, useLayers, useMatchup, useSelection, useTimeline } from '../state/store'
import type { DisagreementOut, Formation, Heatmap, Inference, Matchup, SimilarStatesOut, TacticalBrief, VideoLibrary } from '../types'
import * as echarts from 'echarts'
import { theme } from '../theme'
import BiliPlayer from './video/BiliPlayer'

const TABS = [
  { key: 'heat', label: '条件统计' },
  { key: 'formation', label: '阵型' },
  { key: 'matchup', label: '对手比较' },
  { key: 'ai', label: 'AI分析' },
  { key: 'evidence', label: '历史证据' },
  { key: 'brief', label: '赛前战术卡' },
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
        {tab === 'ai' && <AiTab />}
        {tab === 'evidence' && <EvidenceTab />}
        {tab === 'brief' && <BriefTab />}
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

function AiTab() {
  const gameId = useSelection((s) => s.gameId)
  const selectGame = useSelection((s) => s.selectGame)
  const time = useTimeline((s) => s.time)
  const seek = useTimeline((s) => s.seek)
  const setAI = useAI((s) => s.setAI)
  const layers = useLayers((s) => s.layers)
  const setLayer = useLayers((s) => s.setLayer)
  const [algo, setAlgo] = useState('bc')
  const [rt, setRt] = useState('步兵3')
  const [result, setResult] = useState<Inference | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [dis, setDis] = useState<DisagreementOut | null>(null)
  const [disLoading, setDisLoading] = useState(false)
  const [disErr, setDisErr] = useState('')
  const [sim, setSim] = useState<SimilarStatesOut | null>(null)
  const [simLoading, setSimLoading] = useState(false)
  const [simErr, setSimErr] = useState('')

  const MODEL_STATE: Record<string, string> = {
    bc: 'BC', iql: 'IQL', dt: 'Decision Transformer',
  }

  const runNow = () => {
    if (!gameId) { setErr('请先选择一场比赛'); return }
    setErr(''); setLoading(true)
    Promise.all([
      api.inference({ game_id: gameId, t: Math.floor(time), camp: '红', rtype: rt, algo }),
      api.state(gameId, Math.floor(time)),
    ]).then(([r, st]) => {
      setResult(r)
      const ego = st.robots.find((b) => b.camp === '红' && b.rtype === rt)
      setAI(r.human && (r.human as { alive?: boolean }).alive !== false
        ? { egoX: ego ? ego.x : 14, egoY: ego ? ego.y : 7.5,
          gx: r.goal_dx, gy: r.goal_dy,
          label: `${MODEL_STATE[algo]} · 目标 ${r.target_label}` }
        : null)
      setLayer('rl', true)
    })
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false))
  }

  const scanAll = () => {
    if (!gameId) { setDisErr('请先选择一场比赛'); return }
    setDisErr(''); setDisLoading(true); setDis(null)
    api.disagreements({ game_id: gameId, algo, rtype: rt, top_k: 20, step: 1 })
      .then(setDis)
      .catch((e) => setDisErr(String(e)))
      .finally(() => setDisLoading(false))
  }

  const findSimilar = () => {
    if (!gameId) { setSimErr('请先选择一场比赛'); return }
    setSimErr(''); setSimLoading(true); setSim(null)
    api.similarStates({ game_id: gameId, t: Math.floor(time), camp: '红', rtype: rt, top_k: 20 })
      .then(setSim)
      .catch((e) => setSimErr(String(e)))
      .finally(() => setSimLoading(false))
  }

  const jumpTo = (t: number) => {
    seek(Math.max(0, t - 2))
    setLayer('rl', true)
  }

  const jumpToMatch = (gid: number, t: number) => {
    selectGame(gid)
    setTimeout(() => seek(Math.max(0, t - 2)), 400)
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 16 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div>
          <label className="dim" style={{ fontSize: 12 }}>模型</label>
          <select value={algo} onChange={(e) => setAlgo(e.target.value)}
            style={{ width: '100%', marginTop: 2 }}>
            {Object.entries(MODEL_STATE).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="dim" style={{ fontSize: 12 }}>兵种</label>
          <select value={rt} onChange={(e) => setRt(e.target.value)}
            style={{ width: '100%', marginTop: 2 }}>
            {['步兵3', '步兵4', '英雄', '哨兵', '工程', '空中'].map((x) => (
              <option key={x} value={x}>{x}</option>
            ))}
          </select>
        </div>
        <button className="btn primary" onClick={runNow} disabled={loading || !gameId}>
          {loading ? '推理中…' : `分析当前局面（${Math.floor(time)}s）`}
        </button>
        <button className="btn" onClick={findSimilar} disabled={simLoading || !gameId}>
          {simLoading ? '检索中…' : '查找相似历史局面'}
        </button>
        <button className="btn" onClick={scanAll} disabled={disLoading || !gameId}>
          {disLoading ? '扫描中…' : '扫描全场人机分歧 Top 20'}
        </button>
        {err && <div className="empty">{err}</div>}
        {disErr && <div className="empty">{disErr}</div>}
        {simErr && <div className="empty">{simErr}</div>}
        <div className="dim" style={{ fontSize: 10.5 }}>
          {result?.human && (result.human as { alive?: boolean }).alive === false
            ? '当前机器人已阵亡，无真人动作可对比'
            : '青色箭头 = 模型建议移动方向/距离；真人实际动作来自官方日志（历史统计，不表示 AI 更正确）。'}
          {!layers.rl && ' 打开「RL建议」图层以在地图上显示。'}
        </div>
      </div>
      <div>
        {result && (
          <div style={{ marginBottom: 12 }}>
            <div className="dim" style={{ fontSize: 12, marginBottom: 6 }}>
              {MODEL_STATE[algo]} 建议 · t={result.t}s
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <div className="metric-chip">
                <div className="dim">移动</div>
                <div>
                  {result.goal_dx.toFixed(1)}m, {result.goal_dy.toFixed(1)}m
                  （{Math.hypot(result.goal_dx, result.goal_dy).toFixed(1)}m）
                </div>
              </div>
              <div className="metric-chip">
                <div className="dim">目标</div>
                <div>{result.target_label} {Math.round(result.target_conf * 100)}%</div>
              </div>
              <div className="metric-chip">
                <div className="dim">开火</div>
                <div>{result.fire ? '允许' : '不建议'}</div>
              </div>
              {result.agree.score !== undefined && (
                <div className="metric-chip">
                  <div className="dim">人机分歧</div>
                  <div style={{ color: Number(result.agree.score) > 1 ? 'var(--warn)' : 'inherit' }}>
                    {String(result.agree.score)}
                  </div>
                </div>
              )}
            </div>
            {result.human && (result.human as { alive?: boolean }).alive !== false && (
              <div className="sample-line" style={{ marginTop: 6 }}>
                真人实际：移动 {Number((result.human as { goal_dx?: number }).goal_dx ?? 0).toFixed(1)}m,
                {Number((result.human as { goal_dy?: number }).goal_dy ?? 0).toFixed(1)}m · 开火
                {(result.human as { fire?: boolean }).fire ? '是' : '否'}
              </div>
            )}
          </div>
        )}
        {!result && !err && <div className="empty">选择模型后分析当前局面</div>}

        {dis && (
          <div>
            <div className="dim" style={{ fontSize: 12, marginBottom: 4 }}>
              人机分歧 Top {dis.items.length}（{dis.note}）
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {dis.items.length === 0 && <div className="empty">未发现显著分歧局面</div>}
              {dis.items.map((d, i) => (
                <button key={i} onClick={() => jumpTo(d.t)}
                  style={{ display: 'flex', justifyContent: 'space-between',
                    background: 'var(--panel-alt)', border: '1px solid var(--border)',
                    borderRadius: 4, padding: '6px 8px', cursor: 'pointer',
                    color: 'inherit', fontFamily: 'inherit', fontSize: 12,
                    textAlign: 'left', gap: 8 }}>
                  <span>#{i + 1} · {d.camp}方 {d.rtype} · t={Math.round(d.t)}s</span>
                  <span style={{ color: d.score > 1.5 ? 'var(--warn)' : 'var(--ai)' }}>
                    分歧 {d.score}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {sim && (
          <div>
            <div className="dim" style={{ fontSize: 12, marginBottom: 4 }}>
              相似历史局面 Top {sim.items.length}（候选 {sim.n_candidates}；{sim.note}）
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {sim.items.length === 0 && <div className="empty">未找到相似局面</div>}
              {sim.items.map((s, i) => (
                <button key={i} onClick={() => jumpToMatch(s.game_id, s.t)}
                  style={{ background: 'var(--panel-alt)', border: '1px solid var(--border)',
                    borderRadius: 4, padding: '6px 8px', cursor: 'pointer',
                    color: 'inherit', fontFamily: 'inherit', fontSize: 12,
                    textAlign: 'left' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span>#{i + 1} 比赛 {s.game_id} · t={Math.round(s.t)}s · {s.camp}方 {s.rtype}</span>
                    <span style={{ color: 'var(--ai)' }}>相似度 {s.similarity.toFixed(3)}</span>
                  </div>
                  <div className="dim" style={{ fontSize: 10.5, marginTop: 2 }}>
                    后续行为：移动 {s.human_next.goal_dx?.toFixed(1) ?? '?'}m,
                    {s.human_next.goal_dy?.toFixed(1) ?? '?'}m · 开火
                    {s.human_next.fire ? '是' : '否'}
                    {s.trajectory.map((p) => ` · +${p.dt}s (${p.x}, ${p.y})`)}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function EvidenceTab() {
  const [lib, setLib] = useState<VideoLibrary[] | null>(null)
  const [assoc, setAssoc] = useState<Record<number, string>>({})
  const [msg, setMsg] = useState('')
  const [previewId, setPreviewId] = useState<number | null>(null)

  useEffect(() => {
    api.videoLibrary().then(setLib).catch(() => setLib([]))
  }, [])

  const associate = async (libId: number) => {
    const gid = Number(assoc[libId])
    if (!gid) { setMsg('请输入 game_id'); return }
    try {
      await api.videoLibraryAssociate(libId, gid)
      setMsg(`已关联 game_id=${gid}，刷新比赛页可见`)
    } catch (e) { setMsg(String(e)) }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div>
        <div className="dim" style={{ fontSize: 12, marginBottom: 6 }}>
          视频库（B站仅存 URL/BVID/元数据，不下载视频）
        </div>
        {!lib && <div className="empty">加载中…</div>}
        {lib && lib.length === 0 && <div className="empty">视频库为空</div>}
        {lib?.map((v) => (
          <div key={v.id} style={{
            border: '1px solid var(--border)', borderRadius: 4, padding: 8, marginBottom: 8,
          }}>
            <div style={{ fontSize: 12.5, fontWeight: 600 }}>{v.title}</div>
            <div className="dim" style={{ fontSize: 11, marginTop: 2 }}>
              {v.bvid} · {v.note || '无备注'}
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 6, alignItems: 'center' }}>
              <a className="btn" style={{ fontSize: 11, textDecoration: 'none' }}
                href={v.url} target="_blank" rel="noopener noreferrer">
                在B站打开
              </a>
              <button className="btn" style={{ fontSize: 11, padding: '3px 8px' }}
                onClick={() => setPreviewId((p) => (p === v.id ? null : v.id))}>
                {previewId === v.id ? '收起预览' : '预览'}
              </button>
              <input
                value={assoc[v.id] ?? ''}
                onChange={(e) => setAssoc((s) => ({ ...s, [v.id]: e.target.value }))}
                placeholder="game_id"
                style={{
                  width: 76, background: 'var(--bg)', border: '1px solid var(--border)',
                  color: 'var(--text)', borderRadius: 3, padding: '3px 6px', fontSize: 11,
                }}
              />
              <button className="btn" style={{ fontSize: 11, padding: '3px 8px' }}
                onClick={() => void associate(v.id)}>
                关联到比赛
              </button>
            </div>
            {previewId === v.id && (
              <div style={{ marginTop: 8 }}>
                <BiliPlayer bvid={v.bvid} startAt={0} seekToken={0} height={180} />
              </div>
            )}
          </div>
        ))}
        {msg && <div className="dim" style={{ fontSize: 11, color: 'var(--ai)' }}>{msg}</div>}
        <div className="dim" style={{ fontSize: 11, marginTop: 8 }}>
          全国赛第五十三场（上海交通大学 vs 广东工业大学，BV18Tup6uEg5）不在 2026
          区域赛数据集中，故置于视频库而非伪造 game_id；如后续数据库包含该场，可用
          game_id 关联后获得完整时间同步。
        </div>
      </div>
      <div>
        <div className="dim" style={{ fontSize: 12, marginBottom: 6 }}>
          事件证据（点击「播放」跳到对应比赛与时刻）
        </div>
        <div className="empty">
          从「战术结论」选择某个行为（如 回防 71%）后展开真实案例，此处将联动地图与录像。
        </div>
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

function BriefTab() {
  const teamId = useSelection((s) => s.teamId)
  const [brief, setBrief] = useState<TacticalBrief | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!teamId) {
      setBrief(null)
      setError('')
      return
    }
    setLoading(true)
    setError('')
    api.tacticalBrief(teamId)
      .then(setBrief)
      .catch(() => setError('生成失败（无该队数据或数据不足）'))
      .finally(() => setLoading(false))
  }, [teamId])

  const jump = (gameId: number, t: number) => {
    useSelection.getState().selectGame(gameId)
    useTimeline.getState().seek(t)
  }

  if (!teamId) return <div className="empty">选择对手后生成赛前战术卡</div>
  if (loading) return <div className="empty">生成战术总结中…（基于真实历史统计，非在线大模型）</div>
  if (error) return <div className="empty">{error}</div>
  if (!brief) return <div className="empty">暂无数据</div>

  return (
    <div className="brief-scroll" style={{ overflow: 'auto', height: '100%' }}>
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: 10, padding: '2px 0 8px',
        borderBottom: '1px solid var(--border)', marginBottom: 10,
      }}>
        <span style={{ fontSize: 15, fontWeight: 700 }}>
          {brief.team} · 赛前战术卡
        </span>
        <span className="dim" style={{ fontSize: 11 }}>
          {brief.n_matches} 场比赛 · 生成于 {brief.generated_at}
        </span>
        <span style={{ marginLeft: 'auto' }}>
          <button className="btn" style={{ fontSize: 11, padding: '3px 10px' }}
            onClick={() => window.print()}>
            打印 / 导出
          </button>
        </span>
      </div>

      {brief.sections.length === 0 && (
        <div className="empty">当前队伍暂无可生成的有效战术规律（样本不足）</div>
      )}

      {brief.sections.map((sec) => (
        <div key={sec.id} style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
            {sec.title}
            <span className="dim" style={{ fontSize: 11, fontWeight: 400, marginLeft: 8 }}>
              {sec.summary}
            </span>
          </div>
          {sec.points.map((p) => (
            <div key={p.id} style={{
              borderLeft: '2px solid var(--ai)', padding: '6px 10px', margin: '6px 0',
              background: 'rgba(255,255,255,0.02)', borderRadius: 3,
            }}>
              <div style={{ fontSize: 12.5 }}>
                {p.finding}
                {p.insufficient && (
                  <span style={{ color: 'var(--warn)', marginLeft: 6, fontSize: 11 }}>
                    样本不足
                  </span>
                )}
              </div>
              <div className="dim" style={{ fontSize: 12, marginTop: 3 }}>
                建议：{p.advice}
              </div>
              {p.cases.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                  {p.cases.map((c, i) => (
                    <button key={i} className="btn" style={{ fontSize: 11, padding: '2px 8px' }}
                      title={`点击跳转到该场比赛 ${Math.round(c.t)}s`}
                      onClick={() => jump(c.game_id, c.t)}>
                      {c.opponent || `比赛${c.game_id}`} · {Math.floor(c.t / 60)}:{String(Math.round(c.t) % 60).padStart(2, '0')}
                      {' '}({c.behavior})
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ))}

      <div className="dim" style={{ fontSize: 11, marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 6 }}>
        {brief.note}
      </div>
    </div>
  )
}
