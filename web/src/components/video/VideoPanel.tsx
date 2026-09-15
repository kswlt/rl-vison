import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import { useTimeline } from '../../state/store'
import type { Video } from '../../types'
import BiliPlayer, { formatT } from './BiliPlayer'

interface Props {
  gameId: number
}

/**
 * Match video panel: shows associated Bilibili videos for the selected game,
 * drives the iframe from the global timeline (game_time -> video_time via
 * offset / piecewise anchors) and provides manual calibration:
 *   [设为比赛开始]  -> anchor(game 0, video <input>)
 *   [新增同步锚点]  -> anchor(game = current t, video <input>)
 */
export default function VideoPanel({ gameId }: Props) {
  const time = useTimeline((s) => s.time)
  const playing = useTimeline((s) => s.playing)
  const [videos, setVideos] = useState<Video[] | null>(null)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [videoTarget, setVideoTarget] = useState(0)
  const [inputVt, setInputVt] = useState('')
  const [seekToken, setSeekToken] = useState(0)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    let cancelled = false
    api.videos(gameId).then((vs) => {
      if (cancelled) return
      setVideos(vs)
      setActiveId((prev) => (prev !== null && vs.some((v) => v.id === prev)
        ? prev : (vs[0]?.id ?? null)))
    }).catch(() => { if (!cancelled) setVideos([]) })
    return () => { cancelled = true }
  }, [gameId])

  const active = useMemo(
    () => videos?.find((v) => v.id === activeId) ?? null,
    [videos, activeId],
  )

  // platform timeline -> bilibili seek target
  useEffect(() => {
    if (!active) { setVideoTarget(0); return }
    if (active.alignment_status !== 'calibrated') return
    let cancelled = false
    api.mapToVideo(active.id, Math.floor(time)).then((r) => {
      if (!cancelled && r.video_time != null) {
        setVideoTarget(r.video_time)
        setSeekToken((k) => k + 1)
      }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [active, time])

  const saveAnchor = async (gameTime: number) => {
    if (!active) return
    const vt = parseFloat(inputVt)
    if (!Number.isFinite(vt) || vt < 0) { setMsg('请输入有效的B站时间（秒）'); return }
    setSaving(true)
    try {
      if (gameTime === 0) {
        // 设为比赛开始: single offset
        await api.addAnchor(active.id, { game_time: 0, video_time: vt, confidence: 1.0 })
      } else {
        await api.addAnchor(active.id, { game_time: gameTime, video_time: vt, confidence: 0.8 })
      }
      setMsg(gameTime === 0
        ? `已设置：比赛开始 = B站 ${formatT(vt)}（offset ${vt}s）`
        : `已新增锚点：比赛 ${formatT(gameTime)} = B站 ${formatT(vt)}`)
      const vs = await api.videos(gameId)
      setVideos(vs)
    } catch (e) {
      setMsg(`保存失败：${String(e)}`)
    } finally {
      setSaving(false)
    }
  }

  if (!videos || videos.length === 0) {
    return (
      <div className="video-panel-wrap">
        <div className="panel" style={{ padding: 8 }}>
          <div className="dim" style={{ fontSize: 11 }}>录像</div>
          <div className="empty" style={{ fontSize: 12, padding: '8px 0' }}>
            未关联录像 —— 可在「历史证据」页从视频库关联
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="video-panel-wrap">
      <div className="panel" style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span className="dim" style={{ fontSize: 11 }}>录像</span>
        {videos.map((v) => (
          <button key={v.id}
            onClick={() => setActiveId(v.id)}
            style={{
              fontSize: 10, padding: '2px 6px', borderRadius: 3, cursor: 'pointer',
              background: v.id === activeId ? 'var(--ai)' : 'transparent',
              color: v.id === activeId ? '#06121a' : 'var(--text-dim)',
              border: '1px solid var(--border)',
            }}>
            {v.id === activeId ? (v.alignment_status === 'calibrated' ? '● 已校准' : '○ 未校准') : v.title.slice(0, 12)}
          </button>
        ))}
      </div>

      {active && (
        <>
          <BiliPlayer bvid={active.bvid} startAt={videoTarget} seekToken={seekToken}
            height={170} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
            <span className="dim">平台 {formatT(time)}</span>
            <span style={{ color: active.alignment_status === 'calibrated'
              ? 'var(--ai)' : 'var(--warn)' }}>
              {active.alignment_status === 'calibrated'
                ? `● 已校准 · B站 ${formatT(videoTarget)}`
                : '○ 未校准'}
            </span>
          </div>
          {!playing && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <input
                type="number" min={0} step={1} value={inputVt}
                onChange={(e) => setInputVt(e.target.value)}
                placeholder="B站秒数"
                style={{
                  width: 84, background: 'var(--bg)', border: '1px solid var(--border)',
                  color: 'var(--text)', borderRadius: 3, padding: '3px 6px', fontSize: 11,
                }}
              />
              <button className="btn" style={{ fontSize: 11, padding: '3px 8px' }}
                disabled={saving} onClick={() => void saveAnchor(0)}>
                设为比赛开始
              </button>
              <button className="btn" style={{ fontSize: 11, padding: '3px 8px' }}
                disabled={saving} onClick={() => void saveAnchor(Math.floor(time))}>
                新增锚点({formatT(time)})
              </button>
            </div>
          )}
          {playing && (
            <div className="dim" style={{ fontSize: 10 }}>
              暂停后可进行时间标定
            </div>
          )}
          {msg && <div className="dim" style={{ fontSize: 10, color: 'var(--ai)' }}>{msg}</div>}
        </>
      )}
      </div>
    </div>
  )
}
