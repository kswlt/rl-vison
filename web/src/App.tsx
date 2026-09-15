import { useEffect } from 'react'
import { useSelection } from './state/store'
import Header from './components/Header'
import FilterBar from './components/FilterBar'
import Timeline from './components/Timeline'
import OpponentPanel from './components/OpponentPanel'
import TacticalMap from './components/TacticalMap'
import ConclusionsPanel from './components/ConclusionsPanel'
import TabsPanel from './components/TabsPanel'

export default function App() {
  const loadTeams = useSelection((s) => s.loadTeams)

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
        </div>
        <ConclusionsPanel />
      </div>
      <Timeline />
      <TabsPanel />
    </div>
  )
}
