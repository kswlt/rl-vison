import { useEffect, useRef, useState } from 'react'
import { useSelection, useTimeline } from '../state/store'
import { api } from '../api/client'
import type { MatchTimeline } from '../types'

export default function Timeline() {
  const time = useTimeline((s) => s.time)
  const playing = useTimeline((s) => s.playing)
  const speed = useTimeline((s) => s.speed)
  const duration = useTimeline((s) => s.duration)
  const toggle = useTimeline((s) => s.toggle)
  const step = useTimeline((s) => s.step)
  const setSpeed = useTimeline((s) => s.setSpeed)
  const seek = useTimeline((s) => s.seek)
  const setDuration = useTimeline((s) => s.setDuration)
  const gameId = useSelection((s) => s.gameId)
  const [tl, setTl] = useState<MatchTimeline | null>(null)
  const trackRef = useRef<HTMLDivElement>(null)

  // load timeline for the selected game
  useEffect(() => {
    if (gameId == null) {
      setTl(null)
      return
    }
    api.timeline(gameId).then((t) => {
      setTl(t)
      setDuration(t.duration)
    }).catch(() => setTl(null))
  }, [gameId, setDuration])

  // animation loop (global tactical time)
  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(() => {
      step(speed)
    }, 1000)
    return () => window.clearInterval(id)
  }, [playing, speed, step])

  // markers from timeline events
  const markers = tl?.points
    .map((p) => ({ t: p.t, events: p.events }))
    .filter((p) => p.events.length > 0) ?? []

  const fmt = (t: number) => {
    const s = Math.max(0, Math.floor(t))
    return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  }

  const onTrackClick = (e: React.MouseEvent) => {
    const el = trackRef.current
    if (!el || duration <= 0) return
    const rect = el.getBoundingClientRect()
    const frac = (e.clientX - rect.left) / rect.width
    seek(frac * duration)
  }

  const pct = duration > 0 ? Math.min(100, (time / duration) * 100) : 0

  return (
    <div className="timeline-bar">
      <div className="tl-controls">
        <button className="btn" onClick={() => step(-10)} title="-10s">⏪10</button>
        <button className="btn primary" onClick={toggle} style={{ minWidth: 52 }}>
          {playing ? '⏸ 暂停' : '▶ 播放'}
        </button>
        <button className="btn" onClick={() => step(10)} title="+10s">10⏩</button>
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}
          style={{ width: 62 }}>
          <option value={0.5}>0.5x</option>
          <option value={1}>1x</option>
          <option value={2}>2x</option>
          <option value={4}>4x</option>
        </select>
      </div>

      <div className="tl-track" ref={trackRef} onClick={onTrackClick}>
        <div className="base" />
        <div className="fill" style={{ width: `${pct}%` }} />
        <div className="handle" style={{ left: `${pct}%` }} />
        <div className="tl-markers">
          {markers.map((m, i) => {
            const left = (m.t / Math.max(duration, 1)) * 100
            const kind = m.events.some((e) => e.includes('阵亡'))
              ? 'death'
              : m.events.some((e) => e.includes('前哨'))
                ? 'outpost'
                : m.events.some((e) => e.includes('基地'))
                  ? 'base'
                  : 'phase'
            return <span key={i} className={`mk ${kind}`} style={{ left: `${left}%` }} />
          })}
        </div>
      </div>

      <div className="tl-time mono">{fmt(time)} / {fmt(duration)}</div>
    </div>
  )
}
