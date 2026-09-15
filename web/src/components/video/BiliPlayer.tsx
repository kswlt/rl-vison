import { useEffect, useState } from 'react'
import { theme } from '../../theme'

interface BiliPlayerProps {
  bvid: string
  /** seconds in the Bilibili video the player should start at */
  startAt: number
  /** bump this counter to force a re-seek (reload iframe with new t) */
  seekToken: number
  height?: number
}

/**
 * Official embeddable Bilibili player (player.bilibili.com iframe).
 * Platform timeline stays authoritative: we seek by reloading the iframe
 * with a new t parameter (cross-origin reads are not relied on).
 * Danmaku off by default, no autoplay.
 */
export default function BiliPlayer({ bvid, startAt, seekToken, height = 180 }: BiliPlayerProps) {
  const [failed, setFailed] = useState(false)
  const t = Math.max(0, Math.round(startAt))
  const src = `https://player.bilibili.com/player.html?bvid=${bvid}&t=${t}&danmaku=0&autoplay=0&high_quality=1`

  useEffect(() => { setFailed(false) }, [seekToken, bvid])

  const openInBilibili = () => {
    window.open(`https://www.bilibili.com/video/${bvid}/?t=${t}`, '_blank', 'noopener')
  }

  return (
    <div style={{ position: 'relative', width: '100%', height, background: '#0a0e14',
      borderRadius: 4, overflow: 'hidden' }}>
      {failed ? (
        <div style={{ position: 'absolute', inset: 0, display: 'flex',
          flexDirection: 'column', gap: 8, alignItems: 'center', justifyContent: 'center' }}>
          <span className="dim" style={{ fontSize: 12 }}>B站播放器加载失败</span>
          <button className="btn" onClick={openInBilibili}>在B站打开</button>
        </div>
      ) : (
        <iframe
          key={`${bvid}-${seekToken}-${t}`}
          src={src}
          title="bilibili"
          allowFullScreen
          style={{ width: '100%', height: '100%', border: 'none' }}
          onError={() => setFailed(true)}
        />
      )}
      <div style={{ position: 'absolute', left: 6, top: 4, fontSize: 10,
        color: theme.textFaint, background: 'rgba(10,14,20,.75)', padding: '1px 6px',
        borderRadius: 3 }}>
        B站 {formatT(t)}
      </div>
    </div>
  )
}

export function formatT(s: number): string {
  const sec = Math.max(0, Math.floor(s))
  const m = Math.floor(sec / 60)
  const ss = sec % 60
  return `${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}
