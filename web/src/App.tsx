import { useEffect } from 'react'
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

  useEffect(() => {
    void loadTeams()
  }, [loadTeams])

  return (
    <div className="app">
      <Header />
      <FilterBar />
      <div className="main">
        <OpponentPanel />
        <div className="panel map-panel">
          <TacticalMap />
          {gameId && <VideoPanel gameId={gameId} />}
        </div>
        <ConclusionsPanel />
      </div>
      <Timeline />
      <TabsPanel />
    </div>
  )
}
