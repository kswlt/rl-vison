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

  useEffect(() => {
    void loadTeams()
  }, [loadTeams])

  return (
    <div className="app">
      <Header />
      <FilterBar />

      {/* view switch: replay = map + video split; analytics = full analysis */}
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

      {/* replay view: map left, video right; analytics view: map full */}
      {view === 'replay' ? (
        <div className="replay-split">
          <div className="map-full">
            <TacticalMap />
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
          </div>
          <div className="video-pane">
            {gameId ? <VideoPanel gameId={gameId} /> : (
              <div className="video-empty">选择比赛后在此显示B站录像</div>
            )}
          </div>
        </div>
      ) : (
        <div className="map-full">
          <TacticalMap />
          {gameId && <VideoPanel gameId={gameId} />}
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
      )}

      <Timeline />
      {view === 'analytics' && <TabsPanel />}
    </div>
  )
}
