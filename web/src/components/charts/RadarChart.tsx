import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import type { TeamProfileMetric } from '../../types'
import { theme } from '../../theme'

interface Props {
  metrics: TeamProfileMetric[]
  height?: number
}

/** Radar as a *summary only* — the numeric comparison table carries the data. */
export default function RadarChart({ metrics, height = 220 }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || metrics.length < 3) return
    const chart = echarts.init(ref.current)
    // normalise each metric to a 0..1 comparable scale
    const keys = metrics.slice(0, 8).map((m) => m.key)
    const teamVals = metrics.slice(0, 8).map((m) => _norm(m.value, m))
    const leagueVals = metrics.slice(0, 8).map((m) => _norm(m.league_avg, m))
    chart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      radar: {
        indicator: keys.map((_k, i) => ({ name: metrics[i].label.slice(0, 8), max: 1 })),
        radius: '62%',
        axisName: { color: theme.textDim, fontSize: 10 },
        splitLine: { lineStyle: { color: theme.borderStrong } },
        splitArea: { areaStyle: { color: ['transparent', '#ffffff08'] } },
        axisLine: { lineStyle: { color: theme.borderStrong } },
      },
      series: [{
        type: 'radar',
        data: [
          { value: teamVals, name: '本队', areaStyle: { color: '#3fc9c933' },
            lineStyle: { color: theme.ai }, itemStyle: { color: theme.ai } },
          { value: leagueVals, name: '联盟平均', areaStyle: { opacity: 0 },
            lineStyle: { color: theme.textFaint, type: 'dashed' },
            itemStyle: { color: theme.textFaint } },
        ],
      }],
      legend: { textStyle: { color: theme.textDim, fontSize: 10 }, top: 0 },
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
    }
  }, [metrics])

  return <div ref={ref} style={{ height, width: '100%' }} />
}

function _norm(v: number, m: TeamProfileMetric): number {
  // percent-style metrics are already 0..100; aggression is a ratio ~1
  if (m.unit === '%') return Math.min(1, Math.max(0, v / 100))
  if (m.key === 'aggression') return Math.min(1, v / 2)
  if (m.key === 'formation_stab') return Math.min(1, v / 5)
  if (m.key === 'fallback_speed') return Math.min(1, Math.max(0, 1 - v / 30))
  return Math.min(1, Math.max(0, v))
}
