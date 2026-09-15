import { useEffect, useState } from 'react'
import { useSelection } from './state/store'
import Header from './components/Header'
import FilterBar from './components/FilterBar'
import Timeline from './components/Timeline'
import OpponentPanel from './components/OpponentPanel'
import TacticalMap from './components/TacticalMap'
import ConclusionsPanel from './components/ConclusionsPanel'
import TabsPanel from './components/TabsPanel'

export default function App() {
  const loadTeams = useSelection((s: any) => s.loadTeams)
  const [leftOpen, setLeftOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)
  const [view, setView] = useState<'replay' | 'analytics'>('replay')

  useEffect(() => { void loadTeams() }, [loadTeams])

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
