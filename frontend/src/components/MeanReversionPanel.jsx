import { useState, useEffect, useCallback } from 'react'
import Plot from 'react-plotly.js'
import { runMeanReversion } from '../api'

const MONO = "'JetBrains Mono', monospace"
const DM = "'DM Sans', sans-serif"

const METRICS = [
  { id: 'price', label: 'PRICE' },
  { id: 'log_price', label: 'LOG PRICE' },
  { id: 'realized_vol', label: 'REALIZED VOL' },
]

/**
 * REVERSION — descriptive mean-reversion diagnostics.
 *
 * Visual layer: for any metric, shows whether it mean-reverts (OU half-life,
 * Hurst, ADF t-stat), how far it currently sits from its long-run mean (z),
 * and whether the speed of reversion is itself converging (rolling half-life).
 * Explicitly NOT a signal generator — a lens for spotting behaviour by eye.
 */
export default function MeanReversionPanel({ candles, ticker, timeframe = '1day', assetClass = 'stocks' }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [metric, setMetric] = useState('price')

  const run = useCallback(async () => {
    if (!candles || candles.length < 30) {
      setError('Need at least 30 candles. Run Fetch & Analyze first.')
      return
    }
    setLoading(true); setError(null)
    try {
      const res = await runMeanReversion({ candles, timeframe, asset_class: assetClass })
      setData(res)
    } catch (e) {
      setError(e?.message || String(e))
    } finally {
      setLoading(false)
    }
  }, [candles, timeframe, assetClass])

  // Auto-run whenever the underlying candle set changes.
  useEffect(() => { if (candles && candles.length >= 30) run() }, [candles])

  if (!candles || candles.length < 30) {
    return <div style={S.empty}>Run Fetch & Analyze first — mean-reversion needs ≥30 candles.</div>
  }

  const m = data?.metrics?.[metric]

  return (
    <div style={S.container}>
      <div style={S.header}>
        <div style={S.headerTitle}>
          <span style={S.headerIcon}>↻</span>
          MEAN-REVERSION DIAGNOSTICS{ticker ? ` — ${ticker}` : ''}
        </div>
        <div style={S.headerSub}>
          OU half-life · Hurst exponent · Dickey-Fuller t-stat · rolling half-life. Descriptive — not a trade signal.
        </div>
      </div>

      <div style={S.metricBar}>
        {METRICS.map(mt => (
          <button key={mt.id} onClick={() => setMetric(mt.id)}
            style={{ ...S.metricBtn, ...(metric === mt.id ? S.metricBtnActive : {}) }}>
            {mt.label}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button onClick={run} disabled={loading} style={S.refreshBtn}>
          {loading ? '⟳ computing…' : '↻ recompute'}
        </button>
      </div>

      {error && <div style={S.error}>{error}</div>}
      {loading && !m && <div style={S.empty}>Computing diagnostics…</div>}

      {m && m.error && <div style={S.empty}>{m.label}: {m.error}</div>}

      {m && !m.error && (
        <>
          <StatsRow m={m} />
          <div style={S.chartsCol}>
            <SeriesChart m={m} />
            <RollingHalfLifeChart m={m} />
          </div>
        </>
      )}
    </div>
  )
}

function StatsRow({ m }) {
  const v = verdictStyle(m.verdict)
  return (
    <div style={S.statsRow}>
      <Stat label="VERDICT" value={m.verdict?.toUpperCase()} color={v.color} big />
      <Stat label="HALF-LIFE" value={m.half_life != null ? `${m.half_life} bars` : '—'}
        hint={m.half_life != null ? 'time to revert halfway' : 'no finite reversion'} />
      <Stat label="HURST (H)" value={m.hurst != null ? m.hurst.toFixed(3) : '—'}
        hint={hurstHint(m.hurst)} color={hurstColor(m.hurst)} />
      <Stat label="DF t-STAT" value={m.adf_tstat != null ? m.adf_tstat.toFixed(2) : '—'}
        hint={m.adf_tstat != null && m.adf_tstat < -2.86 ? 'rejects unit root (5%)' : 'weak / no rejection'}
        color={m.adf_tstat != null && m.adf_tstat < -2.86 ? '#22c55e' : '#9ca3af'} />
      <Stat label="Z-SCORE" value={m.z_score != null ? m.z_score.toFixed(2) : '—'}
        hint="current dev. from mean" color={zColor(m.z_score)} />
    </div>
  )
}

function Stat({ label, value, hint, color, big }) {
  return (
    <div style={S.stat}>
      <div style={S.statLabel}>{label}</div>
      <div style={{ ...S.statValue, color: color || '#e5e7eb', fontSize: big ? 15 : 14 }}>{value}</div>
      {hint && <div style={S.statHint}>{hint}</div>}
    </div>
  )
}

function SeriesChart({ m }) {
  const ts = m.series.timestamps.map(t => new Date(t))
  const vals = m.series.values
  const mean = m.mean, std = m.std
  const band = (k) => ({
    type: 'scatter', mode: 'lines', x: [ts[0], ts[ts.length - 1]],
    y: [mean + k * std, mean + k * std], hoverinfo: 'skip', showlegend: false,
    line: { color: k === 0 ? '#ff8000' : '#3b3f52', width: k === 0 ? 1.5 : 1, dash: k === 0 ? 'solid' : 'dot' },
  })
  return (
    <Plot
      data={[
        band(2), band(1), band(0), band(-1), band(-2),
        { type: 'scatter', mode: 'lines', name: m.label, x: ts, y: vals, line: { color: '#ff9e40', width: 1.3 } },
      ]}
      layout={{
        ...darkLayout(`${m.label} — with long-run mean (±1σ, ±2σ)`),
        xaxis: { ...darkAxis, type: 'date' },
        yaxis: { ...darkAxis },
        margin: { l: 60, r: 15, t: 36, b: 30 }, showlegend: false,
      }}
      config={plotConfig} style={{ width: '100%', height: 300 }} useResizeHandler
    />
  )
}

function RollingHalfLifeChart({ m }) {
  const rh = m.rolling_half_life
  if (!rh || !rh.timestamps?.length) {
    return <div style={S.subEmpty}>Not enough data for a rolling half-life series.</div>
  }
  const ts = rh.timestamps.map(t => new Date(t))
  return (
    <Plot
      data={[
        {
          type: 'scatter', mode: 'lines+markers', name: 'Rolling half-life',
          x: ts, y: rh.values, connectgaps: false,
          line: { color: '#f59e0b', width: 1.4 }, marker: { size: 3, color: '#f59e0b' },
        },
      ]}
      layout={{
        ...darkLayout('Rolling half-life — is the speed of reversion converging?'),
        xaxis: { ...darkAxis, type: 'date' },
        yaxis: { ...darkAxis, title: { text: 'half-life (bars)', font: { color: '#6b7280', size: 10, family: MONO } } },
        margin: { l: 60, r: 15, t: 36, b: 30 }, showlegend: false,
      }}
      config={plotConfig} style={{ width: '100%', height: 260 }} useResizeHandler
    />
  )
}

// ── helpers ──
function verdictStyle(v) {
  if (v === 'mean-reverting') return { color: '#22c55e' }
  if (v === 'trending') return { color: '#f59e0b' }
  if (v === 'random walk') return { color: '#9ca3af' }
  return { color: '#6b7280' }
}
function hurstHint(h) {
  if (h == null) return ''
  if (h < 0.45) return 'H<0.5 → anti-persistent'
  if (h > 0.55) return 'H>0.5 → persistent/trend'
  return 'H≈0.5 → random walk'
}
function hurstColor(h) {
  if (h == null) return '#9ca3af'
  if (h < 0.45) return '#22c55e'
  if (h > 0.55) return '#f59e0b'
  return '#9ca3af'
}
function zColor(z) {
  if (z == null) return '#9ca3af'
  if (Math.abs(z) > 2) return '#ef4444'
  if (Math.abs(z) > 1) return '#f59e0b'
  return '#22c55e'
}

const darkAxis = {
  gridcolor: '#1a1d25', linecolor: '#1a1d25', zerolinecolor: '#1a1d25',
  tickfont: { color: '#6b7280', size: 10, family: MONO },
}
const darkLayout = (title) => ({
  title: { text: title, font: { color: '#d1d5db', size: 12, family: DM }, x: 0.02 },
  paper_bgcolor: '#000000', plot_bgcolor: '#0a0a0a',
  font: { color: '#9ca3af', family: DM }, hovermode: 'x unified',
})
const plotConfig = { responsive: true, displayModeBar: false, displaylogo: false }

const S = {
  container: { display: 'flex', flexDirection: 'column', gap: 0 },
  header: { padding: '12px 16px', background: '#0a0a0a', borderBottom: '1px solid #1a1d25' },
  headerTitle: {
    fontSize: 12, fontWeight: 700, fontFamily: MONO, color: '#d1d5db',
    letterSpacing: 1.2, display: 'flex', alignItems: 'center', gap: 8,
  },
  headerIcon: { fontSize: 16, color: '#f59e0b' },
  headerSub: { fontSize: 10, color: '#4b5563', fontFamily: MONO, marginTop: 3, fontStyle: 'italic' },
  metricBar: {
    display: 'flex', alignItems: 'center', gap: 4, padding: '8px 12px',
    background: '#000000', borderBottom: '1px solid #1a1d25',
  },
  metricBtn: {
    background: '#111318', border: '1px solid #1a1d25', color: '#6b7280',
    fontFamily: MONO, fontSize: 10, fontWeight: 600, letterSpacing: 0.8,
    padding: '5px 12px', borderRadius: 4, cursor: 'pointer',
  },
  metricBtnActive: { color: '#e5e7eb', borderColor: '#f59e0b', background: '#1a1410' },
  refreshBtn: {
    background: 'transparent', border: '1px solid #1a1d25', color: '#9ca3af',
    fontFamily: MONO, fontSize: 10, padding: '5px 10px', borderRadius: 4, cursor: 'pointer',
  },
  error: { padding: '10px 16px', color: '#fca5a5', fontFamily: MONO, fontSize: 11, background: '#1a0f0f' },
  empty: { padding: 50, textAlign: 'center', color: '#4b5563', fontFamily: MONO, fontSize: 12 },
  subEmpty: { padding: 24, textAlign: 'center', color: '#4b5563', fontFamily: MONO, fontSize: 11 },
  statsRow: {
    display: 'flex', gap: 1, padding: '10px 12px', background: '#000000',
    borderBottom: '1px solid #1a1d25', flexWrap: 'wrap',
  },
  stat: {
    flex: 1, minWidth: 120, background: '#111318', border: '1px solid #1a1d25',
    borderRadius: 6, padding: '8px 12px', margin: 1,
  },
  statLabel: { fontSize: 8, fontWeight: 700, fontFamily: MONO, color: '#4b5563', letterSpacing: 1.2 },
  statValue: { fontWeight: 800, fontFamily: MONO, marginTop: 4 },
  statHint: { fontSize: 8.5, color: '#4b5563', fontFamily: MONO, marginTop: 3 },
  chartsCol: { display: 'flex', flexDirection: 'column', gap: 0 },
}
