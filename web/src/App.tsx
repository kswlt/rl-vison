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

export default function App() {
  const loadTeams = useSelection((s) => s.loadTeams)
  const gameId = useSelection((s) => s.gameId)
  const [leftOpen, setLeftOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)

  useEffect(() => {
    void loadTeams()
  }, [loadTeams])

  return (
    <div className="app">
      <Header />
      <FilterBar />

      {/* map is the visual centre, fills all space */}
      <div className="map-full">
        <TacticalMap />
        {gameId && <VideoPanel gameId={gameId} />}

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
      <TabsPanel />
    </div>
  )
}
