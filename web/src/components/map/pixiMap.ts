/**
 * PixiJS tactical field renderer — the visual centre of the platform.
 *
 * - 1 Hz referee data is *interpolated* to a smooth 60 FPS display state.
 *   The display clearly separates raw seconds from interpolated frames.
 * - Layer switches (robots / trails / heatmap / flow / …) map onto Pixi
 *   containers so every layer can be toggled live.
 * - Event animations (hit pulse, death flash) are driven from the events API.
 */
import {
  Application, Container, Graphics, Text,
} from 'pixi.js'
import type { EventItem, Flow, Heatmap, MatchState, RobotState } from '../../types'

export const FIELD_X = 28
export const FIELD_Y = 15

const RED = 0xff5b3d
const BLUE = 0x4d9dff
const GOOD = 0x4dd97e
const WARN = 0xf7d154
const DANGER = 0xf85149
const GRID = 0x2a323d
const FIELD_BG = 0x11161d

const TYPE_LABEL: Record<string, string> = {
  英雄: 'H', 工程: 'E', 步兵3: 'I3', 步兵4: 'I4', 空中: 'A', 哨兵: 'S',
  基地: 'B', 前哨站: 'O',
}

interface RobotView {
  id: number
  rtype: string
  camp: '红' | '蓝'
  root: Container
  body: Graphics
  ring: Graphics
  dir: Graphics
  label: Text
  pulseUntil: number   // performance.now() deadline for hit pulse
  deadFlashUntil: number
}

export interface MapLayerFlags {
  robots: boolean
  trail10: boolean
  trailFull: boolean
  heatmap: boolean
  condHeat: boolean
  flow: boolean
  fire: boolean
  hit: boolean
  engage: boolean
  formation: boolean
  routes: boolean
  rl: boolean
  human: boolean
}

export class TacticalField {
  app!: Application
  private mount: HTMLElement
  private world!: Container       // field (grid, base zones)
  private trailLayer!: Container  // robot trails
  private robotLayer!: Container  // robot sprites
  private fxLayer!: Container     // pulses / flashes
  private overlay!: Container     // heatmap / flow placeholder containers
  private robots = new Map<number, RobotView>()
  private states: MatchState[] = []
  private events: EventItem[] = []
  private heat: Heatmap | null = null
  private flow: Flow | null = null
  private overlayLabel: Text | null = null
  private targetTime = 0
  private displayTime = 0
  private scale = 20
  private ox = 0
  private oy = 0
  private flags: MapLayerFlags = {
    robots: true, trail10: true, trailFull: false, heatmap: false,
    condHeat: false, flow: false, fire: false, hit: false, engage: false,
    formation: true, routes: false, rl: true, human: true,
  }
  private readonly timeLabel: Text
  private raf = 0

  constructor(mount: HTMLElement) {
    this.mount = mount
    this.timeLabel = new Text({
      text: '',
      style: { fontFamily: 'Consolas, monospace', fontSize: 11, fill: 0x7d8590 },
    })
    // containers are created eagerly so layer toggles are safe before init()
    this.world = new Container()
    this.trailLayer = new Container()
    this.robotLayer = new Container()
    this.fxLayer = new Container()
    this.overlay = new Container()
  }

  async init(): Promise<void> {
    const app = new Application()
    await app.init({
      resizeTo: this.mount,
      background: FIELD_BG,
      antialias: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      autoDensity: true,
    })
    this.app = app
    this.mount.appendChild(app.canvas)

    app.stage.addChild(this.world)
    app.stage.addChild(this.overlay)
    app.stage.addChild(this.trailLayer)
    app.stage.addChild(this.robotLayer)
    app.stage.addChild(this.fxLayer)
    app.stage.addChild(this.timeLabel)

    this.drawField()
    this.layout()
    this.tick()
  }

  /** Load the full per-second state series for a match (replaces old). */
  setStates(states: MatchState[]): void {
    this.states = states
    this.targetTime = 0
    this.displayTime = 0
    this.robots.clear()
    this.robotLayer.removeChildren()
    // create robot views from the first frame that has the robot
    const first = states[0]
    if (first) {
      for (const r of [...first.robots, ...first.buildings]) {
        this.ensureRobot(r)
      }
    }
  }

  setEvents(events: EventItem[]): void {
    this.events = events
  }

  setTime(t: number): void {
    this.targetTime = Math.max(0, Math.min(this.states.length - 1, t))
  }

  setLayers(flags: MapLayerFlags): void {
    this.flags = flags
    this.applyLayers()
  }

  /** Conditional / occupancy heatmap overlay (null clears it). */
  setHeatmap(heat: Heatmap | null): void {
    this.heat = heat
    this.applyLayers()
  }

  /** Movement flow-field overlay (null clears it). */
  setFlow(flow: Flow | null): void {
    this.flow = flow
    this.applyLayers()
  }

  private applyLayers(): void {
    this.robotLayer.visible = this.flags.robots
    this.trailLayer.visible = this.flags.trail10 || this.flags.trailFull
    const wantHeat = (this.flags.heatmap || this.flags.condHeat) && !!this.heat
    const wantFlow = this.flags.flow && !!this.flow
    this.overlay.visible = wantHeat || wantFlow ||
      this.flags.fire || this.flags.hit || this.flags.engage || this.flags.routes
    if (!this.overlay.visible) {
      this.overlay.removeChildren()
      this.overlayLabel = null
      return
    }
    this.drawOverlay()
  }

  private drawOverlay(): void {
    this.overlay.removeChildren()
    const g = new Graphics()

    if ((this.flags.heatmap || this.flags.condHeat) && this.heat) {
      // single-hue alpha gradient: low sample -> dim, high sample -> solid
      const h = this.heat
      const maxV = Math.max(1, ...h.cells.map((c) => c.count))
      for (const c of h.cells) {
        const alpha = 0.05 + 0.7 * Math.min(1, c.count / maxV)
        g.rect(this.sx(c.x * h.cell_m), this.sy(c.y * h.cell_m),
          this.scale * h.cell_m, this.scale * h.cell_m)
          .fill({ color: 0x3fc9c9, alpha })
      }
      this.overlayLabel = new Text({
        text: `条件热力图 ${h.phase || '全场'} · ${h.rtype || '全部兵种'} · n=${h.n} · ${h.n_matches}场` +
          (h.note ? ` · ${h.note}` : ''),
        style: { fontFamily: 'sans-serif', fontSize: 11, fill: 0x7d8590 },
      })
    } else if (this.flags.flow && this.flow) {
      const f = this.flow
      const maxN = Math.max(1, ...f.cells.map((c) => c.n))
      for (const c of f.cells) {
        if (c.mean_dx === 0 && c.mean_dy === 0) continue
        const cx = this.sx((c.x + 0.5) * f.cell_m)
        const cy = this.sy((c.y + 0.5) * f.cell_m)
        const len = Math.max(4, Math.min(14, c.speed * this.scale * 0.6))
        const ang = Math.atan2(c.mean_dy, c.mean_dx)
        const alpha = 0.15 + 0.6 * Math.min(1, c.n / maxN)
        const ex = cx + Math.cos(ang) * len
        const ey = cy + Math.sin(ang) * len
        g.setStrokeStyle({ width: 1.5, color: 0x9fe8e8, alpha })
        g.moveTo(cx, cy).lineTo(ex, ey)
        // arrow head
        const hx = Math.cos(ang + Math.PI * 0.85) * 3
        const hy = Math.sin(ang + Math.PI * 0.85) * 3
        g.moveTo(ex, ey).lineTo(ex + hx, ey + hy)
      }
      this.overlayLabel = new Text({
        text: `运动流场 ${f.phase || '全场'} · ${f.rtype || '全部兵种'} · n=${f.n} · ${f.n_matches}场`,
        style: { fontFamily: 'sans-serif', fontSize: 11, fill: 0x7d8590 },
      })
    } else {
      // fire / hit / engage / routes layers: honest placeholder until wired
      this.overlayLabel = new Text({
        text: '该图层数据在后续里程碑接入（不提供伪造数据）',
        style: { fontFamily: 'sans-serif', fontSize: 11, fill: 0x7d8590 },
      })
    }

    if (this.overlayLabel) {
      this.overlayLabel.x = this.ox + 8
      this.overlayLabel.y = this.oy + 8
      this.overlay.addChild(this.overlayLabel)
    }
    this.overlay.addChild(g)
  }

  destroy(): void {
    cancelAnimationFrame(this.raf)
    this.app?.destroy(true)
  }

  // -------------------------------------------------------------------------
  layout(): void {
    const w = this.mount.clientWidth || 800
    const h = this.mount.clientHeight || 500
    this.scale = Math.min(w / FIELD_X, h / FIELD_Y)
    this.ox = (w - FIELD_X * this.scale) / 2
    this.oy = (h - FIELD_Y * this.scale) / 2
    this.drawField()
    this.timeLabel.x = 10
    this.timeLabel.y = h - 24
  }

  private sx(x: number): number { return this.ox + x * this.scale }
  private sy(y: number): number { return this.oy + y * this.scale }

  private drawField(): void {
    this.world.removeChildren()
    const g = new Graphics()
    const w = FIELD_X * this.scale
    const h = FIELD_Y * this.scale
    // base fill + half-court tints
    g.rect(this.ox, this.oy, w, h).fill({ color: 0x131a22 })
    g.rect(this.ox, this.oy, w / 2, h).fill({ color: 0xff5b3d, alpha: 0.05 })
    g.rect(this.ox + w / 2, this.oy, w / 2, h).fill({ color: 0x4d9dff, alpha: 0.05 })
    // grid
    g.setStrokeStyle({ width: 1, color: GRID, alpha: 0.6 })
    for (let i = 1; i < FIELD_X; i++) {
      g.moveTo(this.sx(i), this.oy).lineTo(this.sx(i), this.oy + h)
    }
    for (let j = 1; j < FIELD_Y; j++) {
      g.moveTo(this.ox, this.sy(j)).lineTo(this.ox + w, this.sy(j))
    }
    // centre line
    g.setStrokeStyle({ width: 2, color: GRID, alpha: 0.9 })
    g.moveTo(this.ox + w / 2, this.oy).lineTo(this.ox + w / 2, this.oy + h)
    // base zones
    g.setStrokeStyle({ width: 1, color: RED, alpha: 0.5 })
    g.rect(this.ox + 4, this.oy + 4, w * 0.12, h * 0.3)
    g.setStrokeStyle({ width: 1, color: BLUE, alpha: 0.5 })
    g.rect(this.ox + w * 0.88 - 4, this.oy + h * 0.7 - 4, w * 0.12, h * 0.3)
    this.world.addChild(g)
  }

  private ensureRobot(r: RobotState): RobotView {
    let v = this.robots.get(r.robot_id)
    if (v) return v
    const isBuild = r.rtype === '基地' || r.rtype === '前哨站'
    const root = new Container()
    const body = new Graphics()
    const ring = new Graphics()
    const dir = new Graphics()
    const label = new Text({
      text: TYPE_LABEL[r.rtype] ?? String(r.robot_id),
      style: {
        fontFamily: 'Consolas, monospace', fontSize: Math.max(9, this.scale * 0.5),
        fill: 0x0d1117, fontWeight: '700',
      },
    })
    label.anchor.set(0.5)
    root.addChild(dir, body, ring, label)
    v = { id: r.robot_id, rtype: r.rtype, camp: r.camp as '红' | '蓝',
      root, body, ring, dir, label, pulseUntil: 0, deadFlashUntil: 0 }
    this.robots.set(r.robot_id, v)
    this.robotLayer.addChild(root)
    const rOut = isBuild ? this.scale * 0.85 : this.scale * 0.45
    v.body.circle(0, 0, rOut).fill({ color: v.camp === '红' ? RED : BLUE, alpha: 0.9 })
    return v
  }

  private frameAt(idx: number): MatchState | null {
    if (!this.states.length) return null
    const i = Math.max(0, Math.min(this.states.length - 1, Math.round(idx)))
    return this.states[i]
  }

  private tick(): void {
    const loop = () => {
      this.raf = requestAnimationFrame(loop)
      const now = performance.now()
      const n = this.states.length
      if (!n) return

      // smooth-approach the store time; snap on seeks
      let dt = this.targetTime - this.displayTime
      if (Math.abs(dt) > 1.5) this.displayTime = this.targetTime
      else this.displayTime += dt * Math.min(1, 16 / 1000 * 6)

      const t = Math.max(0, this.displayTime)
      const idx = Math.floor(t)
      const frac = t - idx
      const a = this.frameAt(idx)
      const b = this.frameAt(idx + 1)
      if (!a) return
      const l = (v: number, w: number) => v + (w - v) * frac

      // trails (recent 10 s by default, full match when requested)
      this.trailLayer.removeChildren()
      if (this.flags.trail10 || this.flags.trailFull) {
        const trailG = new Graphics()
        const lookback = this.flags.trailFull ? Math.min(120, idx) : 10
        const seen = new Set<number>()
        for (let k = Math.max(0, idx - lookback); k <= idx; k++) {
          const f = this.frameAt(k)
          if (!f) continue
          for (const r of [...f.robots, ...f.buildings]) {
            if (!r.known || !r.alive) continue
            if (seen.has(r.robot_id)) continue
            seen.add(r.robot_id)
            const color = r.camp === '红' ? RED : BLUE
            trailG.setStrokeStyle({ width: 1.2, color, alpha: 0.35 })
            trailG.moveTo(this.sx(r.x), this.sy(r.y))
            for (let k2 = k - 1; k2 >= Math.max(0, idx - lookback); k2--) {
              const f2 = this.frameAt(k2)
              if (!f2) continue
              const r2 = f2.robots.find((q) => q.robot_id === r.robot_id)
              if (r2 && r2.known) {
                trailG.lineTo(this.sx(r2.x), this.sy(r2.y))
                break
              }
            }
          }
        }
        this.trailLayer.addChild(trailG)
      }

      // robots (interpolated display state)
      if (this.flags.robots) {
        for (const v of this.robots.values()) {
          const ra = a.robots.concat(a.buildings).find((q: RobotState) => q.robot_id === v.id)
          const rb = b ? b.robots.concat(b.buildings).find((q: RobotState) => q.robot_id === v.id) : ra
          if (!ra) { v.root.visible = false; continue }
          v.root.visible = true
          const x = rb ? l(ra.x, rb.x) : ra.x
          const y = rb ? l(ra.y, rb.y) : ra.y
          const hp = rb ? l(ra.hp, rb.hp) : ra.hp
          const yaw = rb ? l(ra.yaw, rb.yaw) : ra.yaw
          const known = ra.known || (rb?.known ?? false)
          const alive = ra.alive
          v.root.position.set(this.sx(x), this.sy(y))
          v.root.alpha = known ? (alive ? 1 : 0.35) : 0.15

          // pulse on hit events in this second
          if (now < v.pulseUntil) {
            const p = 1 + 0.35 * (1 - (v.pulseUntil - now) / 250)
            v.root.scale.set(p)
          } else if (now < v.deadFlashUntil) {
            v.root.scale.set(1.15)
          } else {
            v.root.scale.set(1)
          }

          if (v.dir) {
            v.dir.clear()
            const rOut = this.scale * 0.45
            if (ra.yaw_ok) {
              const ang = (yaw * Math.PI) / 180
              v.dir.setStrokeStyle({ width: 2, color: v.camp === '红' ? RED : BLUE, alpha: 0.9 })
              v.dir.moveTo(0, 0).lineTo(Math.cos(ang) * rOut * 1.5, Math.sin(ang) * rOut * 1.5)
            }
          }
          // hp ring
          const maxhp = Math.max(ra.maxhp, rb?.maxhp ?? 0, 1)
          const fracHp = Math.max(0, Math.min(1, hp / maxhp))
          const rOut = this.scale * 0.45
          v.ring.clear()
          v.ring.setStrokeStyle({ width: 2.5, color: 0x21262d })
          v.ring.circle(0, 0, rOut + 3).stroke()
          const ringColor = fracHp > 0.5 ? GOOD : fracHp > 0.25 ? WARN : DANGER
          v.ring.setStrokeStyle({ width: 2.5, color: ringColor })
          v.ring.arc(0, 0, rOut + 3, -Math.PI / 2, -Math.PI / 2 + fracHp * Math.PI * 2).stroke()
          // sync label size
          v.label.style.fontSize = Math.max(9, this.scale * 0.5)
        }
      }

      // event pulses for the current raw second
      const sec = Math.round(t)
      for (const ev of this.events) {
        if (Math.round(ev.t) !== sec) continue
        const v = this.robots.get(ev.robot_id)
        if (!v) continue
        if (ev.etype.includes('受击') || ev.etype.includes('伤害') ||
            ev.etype.includes('命中')) {
          v.pulseUntil = now + 250
        }
        if (ev.etype.includes('阵亡') || ev.etype.includes('摧毁')) {
          v.deadFlashUntil = now + 400
        }
      }

      this.timeLabel.text =
        `t=${sec}s  raw 1Hz  ·  ${t.toFixed(1)}s  interpolated  ·  ${n} 秒数据`
    }
    loop()
  }
}
