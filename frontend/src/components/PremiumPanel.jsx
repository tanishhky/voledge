import Plot from 'react-plotly.js'

const MONO = "'JetBrains Mono', monospace"
const DM = "'DM Sans', sans-serif"

/**
 * PREMIUM — the headline of VolEdge.
 *
 * Pairs the risk-neutral distribution (BKM, from option prices) against the
 * physical distribution (realized, horizon-matched return moments) and shows
 * the spread Q - P for variance, skew, and kurtosis. The spread IS the risk
 * premium — the economic content the platform exists to surface.
 *
 * Unlike the BKM panel (which compares against price-space GMM moments), this
 * uses the backend's statistically-correct, horizon-matched physical RETURN
 * moments, so RN and physical are measured on the same axis.
 */
export default function PremiumPanel({ volData }) {
  if (!volData) return <div style={S.empty}>Run Vol Analysis to compute the risk premium (Q − P)</div>

  const va = volData.volatility_analysis
  const p30 = va?.premium_30d
  const p60 = va?.premium_60d
  const hasData = p30 || p60

  return (
    <div style={S.container}>
      <div style={S.header}>
        <div style={S.headerTitle}>
          <span style={S.headerIcon}>Δ</span>
          THE RISK PREMIUM — Q MINUS P
        </div>
        <div style={S.headerSub}>
          Risk-neutral (option-implied, BKM) minus physical (realized, horizon-matched). The spread is the premium the market pays.
        </div>
      </div>

      {!hasData ? (
        <div style={S.noData}>
          <div style={S.noDataIcon}>◇</div>
          <div style={S.noDataTitle}>Premium unavailable</div>
          <div style={S.noDataSub}>
            Needs both a valid BKM fit (≥3 OTM calls and ≥3 OTM puts in the tenor)
            and enough price history for horizon-matched realized moments.
          </div>
        </div>
      ) : (
        <>
          <div style={S.cardsRow}>
            <PremiumCard label="30-DAY" prem={p30} />
            <PremiumCard label="60-DAY" prem={p60} />
          </div>

          <ReadPanel p30={p30} p60={p60} />

          <div style={S.chartsRow}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <SpreadChart p30={p30} p60={p60} which="vol_premium"
                title="Variance Premium (vol points)" scale={100} unit="%" />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <SpreadChart p30={p30} p60={p60} which="skew_premium"
                title="Skew Premium (RN − physical)" scale={1} unit="" />
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function PremiumCard({ label, prem }) {
  if (!prem) {
    return (
      <div style={{ ...S.card, opacity: 0.5 }}>
        <div style={S.cardLabel}>{label}</div>
        <div style={S.cardNoData}>Insufficient data</div>
      </div>
    )
  }

  return (
    <div style={S.card}>
      <div style={S.cardLabel}>{label}</div>
      <div style={S.compareGrid}>
        <div style={S.colHeader}>MOMENT</div>
        <div style={S.colHeader}>RISK-NEUTRAL</div>
        <div style={S.colHeader}>PHYSICAL</div>
        <div style={S.colHeader}>PREMIUM (Q−P)</div>

        <MomentRow
          name="Volatility"
          rn={fmtPct(prem.rn_volatility)}
          phys={fmtPct(prem.phys_volatility)}
          premium={prem.vol_premium != null ? fmtPctSigned(prem.vol_premium) : 'N/A'}
          premiumColor={signColor(prem.vol_premium, true)}
        />
        <MomentRow
          name="Skewness"
          rn={fmtNum(prem.rn_skewness)}
          phys={fmtNum(prem.phys_skewness)}
          premium={prem.skew_premium != null ? fmtNumSigned(prem.skew_premium) : 'N/A'}
          premiumColor={signColor(prem.skew_premium, false)}
        />
        <MomentRow
          name="Kurtosis"
          rn={fmtNum(prem.rn_kurtosis)}
          phys={fmtNum(prem.phys_kurtosis)}
          premium={prem.kurt_premium != null ? fmtNumSigned(prem.kurt_premium) : 'N/A'}
          premiumColor={signColor(prem.kurt_premium, true)}
        />
        <MomentRow
          name="Variance"
          rn={prem.rn_volatility != null ? (prem.rn_volatility ** 2).toFixed(5) : 'N/A'}
          phys={prem.phys_volatility != null ? (prem.phys_volatility ** 2).toFixed(5) : 'N/A'}
          premium={prem.variance_premium != null ? fmtSigned(prem.variance_premium, 5) : 'N/A'}
          premiumColor={signColor(prem.variance_premium, true)}
        />
      </div>
    </div>
  )
}

function MomentRow({ name, rn, phys, premium, premiumColor }) {
  return (
    <>
      <div style={S.momentLabel}>{name}</div>
      <div style={{ ...S.momentVal, color: '#ff9e40' }}>{rn}</div>
      <div style={{ ...S.momentVal, color: '#29b6f6' }}>{phys}</div>
      <div style={{ ...S.momentVal, color: premiumColor, fontWeight: 800 }}>{premium}</div>
    </>
  )
}

function ReadPanel({ p30, p60 }) {
  const reads = []
  if (p30?.interpretation) reads.push({ tenor: '30d', text: p30.interpretation })
  if (p60?.interpretation) reads.push({ tenor: '60d', text: p60.interpretation })
  if (reads.length === 0) {
    reads.push({ tenor: '', text: 'Risk-neutral and physical moments are broadly aligned — no pronounced premium at these tenors.' })
  }
  return (
    <div style={S.readContainer}>
      <div style={S.readTitle}>THE READ</div>
      {reads.map((r, i) => (
        <div key={i} style={S.readRow}>
          {r.tenor && <span style={S.readTenor}>{r.tenor}</span>}
          <span style={S.readText}>{r.text}</span>
        </div>
      ))}
    </div>
  )
}

function SpreadChart({ p30, p60, which, title, scale, unit }) {
  const labels = []
  const rnVals = []
  const physVals = []

  const rnKey = which === 'vol_premium' ? 'rn_volatility'
    : which === 'skew_premium' ? 'rn_skewness' : 'rn_kurtosis'
  const physKey = which === 'vol_premium' ? 'phys_volatility'
    : which === 'skew_premium' ? 'phys_skewness' : 'phys_kurtosis'

  for (const [lab, p] of [['30d', p30], ['60d', p60]]) {
    if (p && p[rnKey] != null && p[physKey] != null) {
      labels.push(lab)
      rnVals.push(p[rnKey] * scale)
      physVals.push(p[physKey] * scale)
    }
  }
  if (labels.length === 0) return null

  return (
    <Plot
      data={[
        { type: 'bar', name: 'Risk-Neutral', x: labels, y: rnVals, marker: { color: '#ff9e40', opacity: 0.9 } },
        { type: 'bar', name: 'Physical', x: labels, y: physVals, marker: { color: '#29b6f6', opacity: 0.8 } },
      ]}
      layout={{
        ...darkLayout(title),
        barmode: 'group', bargap: 0.3, bargroupgap: 0.15,
        xaxis: { ...darkAxis, title: { text: 'Tenor', font: { color: '#6b7280', size: 11, family: MONO } } },
        yaxis: { ...darkAxis, title: { text: unit || 'value', font: { color: '#6b7280', size: 11, family: MONO } }, ticksuffix: unit },
        margin: { l: 55, r: 15, t: 40, b: 50 },
        legend: { font: { color: '#9ca3af', size: 9, family: MONO }, bgcolor: 'rgba(0,0,0,0)', orientation: 'h', y: -0.22 },
        shapes: [{ type: 'line', x0: -0.5, x1: labels.length - 0.5, y0: 0, y1: 0, line: { color: '#4b5563', width: 1, dash: 'dash' } }],
      }}
      config={plotConfig}
      style={{ width: '100%', height: 320 }}
      useResizeHandler
    />
  )
}

// ── formatting helpers ──
function fmtPct(v) { return v == null ? 'N/A' : `${(v * 100).toFixed(1)}%` }
function fmtPctSigned(v) { return v == null ? 'N/A' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%` }
function fmtNum(v) { return v == null ? 'N/A' : v.toFixed(3) }
function fmtNumSigned(v) { return v == null ? 'N/A' : `${v >= 0 ? '+' : ''}${v.toFixed(3)}` }
function fmtSigned(v, d) { return v == null ? 'N/A' : `${v >= 0 ? '+' : ''}${v.toFixed(d)}` }
// positiveIsRich: when true, a positive premium is "rich" (blue), negative "cheap" (amber)
function signColor(v, positiveIsRich) {
  if (v == null || Math.abs(v) < 1e-9) return '#9ca3af'
  const rich = positiveIsRich ? v > 0 : v < 0
  return rich ? '#ff9e40' : '#f59e0b'
}

const darkAxis = {
  gridcolor: '#1a1d25', linecolor: '#1a1d25', zerolinecolor: '#1a1d25',
  tickfont: { color: '#6b7280', size: 10, family: MONO },
}
const darkLayout = (title) => ({
  title: { text: title, font: { color: '#d1d5db', size: 12, family: DM }, x: 0.02 },
  paper_bgcolor: '#000000', plot_bgcolor: '#0a0a0a',
  font: { color: '#9ca3af', family: DM }, hovermode: 'closest',
})
const plotConfig = { responsive: true, displayModeBar: false, displaylogo: false }

const S = {
  container: { display: 'flex', flexDirection: 'column', gap: 0 },
  header: { padding: '12px 16px', background: '#0a0a0a', borderBottom: '1px solid #1a1d25' },
  headerTitle: {
    fontSize: 12, fontWeight: 700, fontFamily: MONO, color: '#d1d5db',
    letterSpacing: 1.2, display: 'flex', alignItems: 'center', gap: 8,
  },
  headerIcon: { fontSize: 16, color: '#ff8000' },
  headerSub: { fontSize: 10, color: '#4b5563', fontFamily: MONO, marginTop: 3, fontStyle: 'italic' },
  empty: { padding: 60, textAlign: 'center', color: '#4b5563', fontFamily: MONO, fontSize: 12 },
  noData: { padding: 60, textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 },
  noDataIcon: { fontSize: 36, color: '#1e2230' },
  noDataTitle: { fontSize: 14, color: '#6b7280', fontWeight: 500, fontFamily: DM },
  noDataSub: { fontSize: 11, color: '#4b5563', fontFamily: MONO, maxWidth: 420, lineHeight: 1.5 },
  cardsRow: { display: 'flex', gap: 8, padding: '8px 10px', background: '#000000', borderBottom: '1px solid #1a1d25' },
  card: { flex: 1, background: '#111318', borderRadius: 6, border: '1px solid #1a1d25', padding: '10px 14px' },
  cardLabel: { fontSize: 11, fontWeight: 700, fontFamily: MONO, color: '#ff8000', letterSpacing: 1.5, marginBottom: 10 },
  cardNoData: { fontSize: 11, color: '#4b5563', fontFamily: MONO, padding: '20px 0', textAlign: 'center' },
  compareGrid: { display: 'grid', gridTemplateColumns: '78px 1fr 1fr 1fr', gap: '5px 8px', alignItems: 'center' },
  colHeader: {
    fontSize: 8, fontWeight: 700, fontFamily: MONO, color: '#4b5563',
    letterSpacing: 1, paddingBottom: 4, borderBottom: '1px solid #1a1d25',
  },
  momentLabel: { fontSize: 10, fontWeight: 600, fontFamily: MONO, color: '#6b7280' },
  momentVal: { fontSize: 13, fontWeight: 700, fontFamily: MONO, textAlign: 'right' },
  readContainer: { padding: '10px 14px', background: '#0a0a0a', borderBottom: '1px solid #1a1d25' },
  readTitle: { fontSize: 9, fontWeight: 700, fontFamily: MONO, color: '#4b5563', letterSpacing: 1.2, marginBottom: 8 },
  readRow: {
    padding: '8px 12px', borderRadius: 4, marginBottom: 4, display: 'flex',
    alignItems: 'flex-start', gap: 8, background: '#0f0f1a', borderLeft: '3px solid #ff8000',
  },
  readTenor: {
    fontSize: 9, fontWeight: 700, fontFamily: MONO, color: '#ffb46b',
    background: '#1a1530', borderRadius: 3, padding: '2px 6px', flexShrink: 0,
  },
  readText: { color: '#ffb46b', fontSize: 11, lineHeight: 1.5, fontFamily: MONO },
  chartsRow: { display: 'flex', gap: 1, borderBottom: '1px solid #1a1d25' },
}
