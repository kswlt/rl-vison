import { useEffect, useState } from 'react'
import { api } from '../api/client'

export default function Header() {
  const [matches, setMatches] = useState<number | null>(null)

  useEffect(() => {
    api.health().then((h) => setMatches(h.matches)).catch(() => setMatches(null))
  }, [])

  return (
    <div className="header">
      <div className="logo">
        <svg width="22" height="22" viewBox="0 0 64 64">
          <rect width="64" height="64" rx="12" fill="#14181f" />
          <rect x="12" y="12" width="40" height="40" rx="4" fill="none"
            stroke="#3fc9c9" strokeWidth="3" />
          <circle cx="32" cy="24" r="6" fill="#ff5b3d" />
          <path d="M32 34 L32 46 M22 40 L32 46 L42 40" stroke="#e6edf3"
            strokeWidth="3" fill="none" />
        </svg>
        <span>RMUC Tactical <span className="dot">Intelligence</span></span>
      </div>
      <span className="badge">TACTICAL</span>
      <span className="badge live">● LIVE</span>
      <div className="meta">
        {matches !== null ? `${matches} 场比赛 · 4.0M 条逐秒状态` : '连接后端中…'}
      </div>
    </div>
  )
}
