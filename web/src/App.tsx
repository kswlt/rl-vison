import { useEffect, useRef, useState } from 'react'
import { useSelection } from './state/store'
import Header from './components/Header'
import FilterBar from './components/FilterBar'
import Timeline from './components/Timeline'
import OpponentPanel from './components/OpponentPanel'
import TacticalMap from './components/TacticalMap'
import ConclusionsPanel from './components/ConclusionsPanel'
import TabsPanel from './components/TabsPanel'
import VideoPanel from './components/video/VideoPanel'

export default function App() {
  const loadTeams = useSelection((s: any) => s.loadTeams)
  const gameId = useSelection((s: any) => s.gameId)
  const [leftOpen, setLeftOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)
  const [view, setView] = useState<'replay' | 'analytics'>('replay')
  const [videoOpen, setVideoOpen] = useState(true)
  // floating video window position
  const [pos, setPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const dragRef = useRef<{ dx: number; dy: number } | null>(null)

  useEffect(() => { void loadTeams() }, [loadTeams])

  // start drag on the video title bar
  const onDragStart = (e: React.MouseEvent) => {
    const rect = (e.currentTarget.parentElement as HTMLElement).getBoundingClientRect()
    dragRef.current = { dx: e.clientX - rect.left, dy: e.clientY - rect.top }
    const move = (ev: MouseEvent) => {
      if (!dragRef.current) return
      const nx = Math.max(0, Math.min(window.innerWidth - 200, ev.clientX - dragRef.current.dx))
      const ny = Math.max(0, Math.min(window.innerHeight - 100, ev.clientY - dragRef.current.dy))
      setPos({ x: nx, y: ny })
    }
    const up = () => {
      dragRef.current = null
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    e.preventDefault()
  }

  return (
    <div className="app">
      <Header />
      <FilterBar />

      <div className="view-switch">
        <button className={`view-btn ${view === 'replay' ? 'active' : ''}`} onClick={() => setView('replay')}>比赛回放</button>
        <button className={`view-btn ${view === 'analytics' ? 'active' : ''}`} onClick={() => setView('analytics')}>战术分析</button>
      </div>

      <div className="map-full">
        <TacticalMap />

        {gameId && videoOpen && (
          <div className="video-float" style={{ left: pos.x || undefined, top: pos.y || undefined, right: pos.x ? undefined : 12 }}>
            <div className="video-dragbar" onMouseDown={onDragStart}>
              <span style={{ fontSize: 10, color: 'var(--text-dim)', cursor: 'move', padding: '4px 8px' }}>⋮⋮ 拖动</span>
              <button className="video-close" onClick={() => setVideoOpen(false)} title="关闭视频">×</button>
            </div>
            <VideoPanel gameId={gameId} />
          </div>
        )}
        {gameId && !videoOpen && (
          <button className="video-reopen" onClick={() => setVideoOpen(true)}>▶ 视频</button>
        )}

        <button className="drawer-toggle left" onClick={() => setLeftOpen(v => !v)} title="对手画像">
          {leftOpen ? '◂' : '▸'}
        </button>
        <div className={`drawer left-drawer ${leftOpen ? 'open' : ''}`}>
          <OpponentPanel />
        </div>

        <button className="drawer-toggle right" onClick={() => setRightOpen(v => !v)} title="战术结论">
          {rightOpen ? '▸' : '◂'}
        </button>
        <div className={`drawer right-drawer ${rightOpen ? 'open' : ''}`}>
          <ConclusionsPanel />
        </div>
      </div>

      <Timeline />
      {view === 'analytics' && <TabsPanel />}
    </div>
  )
}
