import { useEffect, useState } from 'react'
import { useSelection } from './state/store'
import Header from './components/Header'
import FilterBar from './components/FilterBar'
import Timeline from './components/Timeline'
import OpponentPanel from './components/OpponentPanel'
import TacticalMap from './components/TacticalMap'
import ConclusionsPanel from './components/ConclusionsPanel'
import TabsPanel from './components/TabsPanel'
import VideoPanel from './components/video/VideoPanel'

type View = 'replay' | 'analytics'

export default function App() {
  const loadTeams = useSelection((s) => s.loadTeams)
  const gameId = useSelection((s) => s.gameId)
  const [leftOpen, setLeftOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)
  const [view, setView] = useState<View>('replay')
  const [videoOpen, setVideoOpen] = useState(true)

  useEffect(() => {
    void loadTeams()
  }, [loadTeams])

  return (
    <div className="app">
      <Header />
      <FilterBar />

      {/* view switch */}
      <div className="view-switch">
        <button
          className={`view-btn ${view === 'replay' ? 'active' : ''}`}
          onClick={() => setView('replay')}
        >
          比赛回放
        </button>
        <button
          className={`view-btn ${view === 'analytics' ? 'active' : ''}`}
          onClick={() => setView('analytics')}
        >
          战术分析
        </button>
      </div>

      {/* map fills full screen */}
      <div className="map-full">
        <TacticalMap />

        {/* video as floating small window, top-right corner */}
        {gameId && videoOpen && (
          <div className="video-float">
            <button className="video-close" onClick={() => setVideoOpen(false)} title="关闭视频">×</button>
            <VideoPanel gameId={gameId} />
          </div>
        )}
        {gameId && !videoOpen && (
          <button className="video-reopen" onClick={() => setVideoOpen(true)} title="打开视频">▶ 视频</button>
        )}

        {/* left drawer toggle */}
        <button
          className="drawer-toggle left"
          onClick={() => setLeftOpen(v => !v)}
          title="对手画像"
        >
          {leftOpen ? '◂' : '▸'}
        </button>
        <div className={`drawer left-drawer ${leftOpen ? 'open' : ''}`}>
          <OpponentPanel />
        </div>

        {/* right drawer toggle */}
        <button
          className="drawer-toggle right"
          onClick={() => setRightOpen(v => !v)}
          title="战术结论"
        >
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
