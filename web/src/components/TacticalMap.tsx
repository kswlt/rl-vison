import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useAI, useConditions, useSelection, useTimeline, useLayers, LAYER_DEFS, useMatchup } from '../state/store'
import type { EventItem, Flow, Heatmap, MatchStates, Matchup } from '../types'
import { TacticalField } from './map/pixiMap'
import { theme } from '../theme'

export default function TacticalMap() {
  const mountRef = useRef<HTMLDivElement>(null)
  const fieldRef = useRef<TacticalField | null>(null)
  const [ready, setReady] = useState(false)
  const [loadState, setLoadState] = useState<'idle' | 'loading' | 'ready' | 'empty'>('idle')

  const gameId = useSelection((s) => s.gameId)
  const time = useTimeline((s) => s.time)
  const layers = useLayers((s) => s.layers)
  const toggleLayer = useLayers((s) => s.toggleLayer)
  const conditions = useConditions((s) => s.conditions)
  const matchupSel = useMatchup()
  const aiState = useAI()

  // RL recommendation overlay
  useEffect(() => {
    const field = fieldRef.current
    if (!field || !ready) return
    field.setAI(aiState.ai)
  }, [ready, aiState.ai])

  // load matchup overlay when activated (routes layer shows it)
  useEffect(() => {
    const field = fieldRef.current
    if (!field || !ready) return
    if (!matchupSel.active || !matchupSel.teamA || !matchupSel.teamB) {
      field.setMatchup(null)
      return
    }
    let cancelled = false
    api.matchup(matchupSel.teamA, matchupSel.teamB).then((m: Matchup) => {
      if (!cancelled) field.setMatchup(m)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [ready, matchupSel.active, matchupSel.teamA, matchupSel.teamB])

  // load conditional heatmap / flow overlays when conditions change
  useEffect(() => {
    const field = fieldRef.current
    if (!field || !ready) return
    let cancelled = false

    const wantHeat = layers.heatmap || layers.condHeat
    const wantFlow = layers.flow
    if (wantHeat) {
      api.heatmap(conditions).then((h: Heatmap) => {
        if (!cancelled) field.setHeatmap(h)
      }).catch(() => {})
    } else {
      field.setHeatmap(null)
    }
    if (wantFlow) {
      api.flow(conditions).then((f: Flow) => {
        if (!cancelled) field.setFlow(f)
      }).catch(() => {})
    } else {
      field.setFlow(null)
    }
    return () => { cancelled = true }
  }, [ready, conditions, layers.heatmap, layers.condHeat, layers.flow])

  // init pixi once
  useEffect(() => {
    if (!mountRef.current) return
    const field = new TacticalField(mountRef.current)
    fieldRef.current = field
    void field.init().then(() => {
      setReady(true)
      field.setLayers({
        robots: layers.robots, trail10: layers.trail10, trailFull: layers.trailFull,
        heatmap: layers.heatmap, condHeat: layers.condHeat, flow: layers.flow,
        fire: layers.fire, hit: layers.hit, engage: layers.engage,
        formation: layers.formation, routes: layers.routes,
        rl: layers.rl, human: layers.human,
      })
    })
    const onResize = () => field.layout()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      field.destroy()
      fieldRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // load full state series + events for the selected match
  useEffect(() => {
    const field = fieldRef.current
    if (!field || !ready) return
    if (gameId == null) {
      setLoadState('idle')
      return
    }
    let cancelled = false
    setLoadState('loading')
    Promise.all([
      api.states(gameId, 1),
      api.events(gameId, undefined, 2000).catch(() => [] as EventItem[]),
    ]).then(([states]: [MatchStates, EventItem[]]) => {
      if (cancelled) return
      field.setStates(states.states)
      setLoadState(states.states.length ? 'ready' : 'empty')
    }).catch(() => {
      if (!cancelled) setLoadState('empty')
    })
    return () => { cancelled = true }
  }, [gameId, ready])

  // keep the field's target time in sync with the global tactical time
  useEffect(() => {
    fieldRef.current?.setTime(time)
  }, [time])

  // live layer toggles
  useEffect(() => {
    fieldRef.current?.setLayers({
      robots: layers.robots, trail10: layers.trail10, trailFull: layers.trailFull,
      heatmap: layers.heatmap, condHeat: layers.condHeat, flow: layers.flow,
      fire: layers.fire, hit: layers.hit, engage: layers.engage,
      formation: layers.formation, routes: layers.routes,
      rl: layers.rl, human: layers.human,
    })
  }, [layers])

  const [layersOpen, setLayersOpen] = useState(false)

  return (
    <div className="map-stage" style={{
      backgroundImage: 'url(/api/field/background.jpeg)',
      backgroundSize: '100% 100%',
      backgroundPosition: 'center',
      backgroundColor: '#0d1117',
    }}>
      <div ref={mountRef} style={{ position: 'absolute', inset: 0 }} />

      {!ready && (
        <div style={{ color: theme.textFaint, fontSize: 12 }}>
          初始化渲染器…
        </div>
      )}

      {/* layers control — collapsed by default, toggle button */}
      <div style={{ position: 'absolute', top: 10, right: 10, zIndex: 5 }}>
        <button onClick={() => setLayersOpen(v => !v)} style={{
          background: 'rgba(22,27,34,.92)', border: `1px solid ${theme.borderStrong}`,
          borderRadius: 6, padding: '6px 10px', fontSize: 11, color: theme.text,
          cursor: 'pointer',
        }}>
          Layers {layersOpen ? '▾' : '▸'}
        </button>
        {layersOpen && (
          <div style={{
            marginTop: 4,
            background: 'rgba(22,27,34,.95)', border: `1px solid ${theme.borderStrong}`,
            borderRadius: 6, padding: 8, fontSize: 11, minWidth: 150,
            color: theme.textDim, maxHeight: 'calc(100vh - 200px)', overflowY: 'auto',
          }}>
            {LAYER_DEFS.map((l) => (
              <label key={l.key} style={{ display: 'flex', gap: 6, padding: '1px 0',
                cursor: 'pointer', alignItems: 'center' }}>
                <input type="checkbox" checked={!!layers[l.key]}
                  onChange={() => toggleLayer(l.key)}
                  style={{ accentColor: theme.ai }} />
                {l.label}
              </label>
            ))}
          </div>
        )}
      </div>

      {gameId != null && loadState === 'loading' && (
        <div style={{
          position: 'absolute', bottom: 8, left: 12, fontSize: 11,
          color: theme.textFaint,
        }}>
          加载整场逐秒状态…
        </div>
      )}
      {gameId != null && loadState === 'empty' && (
        <div style={{
          position: 'absolute', bottom: 8, left: 12, fontSize: 11,
          color: theme.warn,
        }}>
          该场比赛暂无可用状态数据
        </div>
      )}
    </div>
  )
}
