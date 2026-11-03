const GRADE_COLORS = {
  A: '#4ade80',
  B: '#86efac',
  C: '#fbbf24',
  D: '#fb923c',
  F: '#f87171',
}

/**
 * score      — the quality_score object from the backend
 * findings   — the full findings array (used to derive accurate counts)
 */
export default function QualityScore({ score, findings = [] }) {
  // Task 2: derive counts from the actual findings array
  const criticalCount = findings.filter(f => f.severity === 'critical').length
  const warningCount  = findings.filter(f => f.severity === 'warning').length
  const infoCount     = findings.filter(f => f.severity === 'info').length

  const color = GRADE_COLORS[score.grade] || '#94a3b8'
  const circumference = 2 * Math.PI * 52
  const offset = circumference * (1 - score.score / 100)

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      padding: '1.5rem',
    }}>
      {/* ── Grade badge — prominent, above everything ── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        marginBottom: '1.1rem',
      }}>
        <span style={{
          fontSize: '2.5rem',
          fontWeight: 700,
          color,
          lineHeight: 1,
          letterSpacing: '-0.03em',
        }}>
          {score.grade}
        </span>
        <div>
          <div style={{ fontWeight: 500, fontSize: '0.9rem', color: 'var(--text)' }}>
            Quality grade
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
            Score {score.score} / 100
          </div>
        </div>
      </div>

      {/* ── Ring + pills row ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
        {/* Ring */}
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <svg width="110" height="110" style={{ transform: 'rotate(-90deg)' }}>
            <circle cx="55" cy="55" r="46"
              fill="none" stroke="var(--border)" strokeWidth="7" />
            <circle cx="55" cy="55" r="46"
              fill="none" stroke={color} strokeWidth="7"
              strokeDasharray={2 * Math.PI * 46}
              strokeDashoffset={2 * Math.PI * 46 * (1 - score.score / 100)}
              strokeLinecap="round"
              style={{ transition: 'stroke-dashoffset 1s ease' }}
            />
          </svg>
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
          }}>
            <span style={{ fontSize: '1.6rem', fontWeight: 600, color, lineHeight: 1 }}>
              {score.score}
            </span>
            <span style={{ fontSize: '0.65rem', color: 'var(--muted)', marginTop: '2px' }}>/ 100</span>
          </div>
        </div>

        {/* Severity pills — using derived counts */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          <Pill count={criticalCount} label="critical" color="var(--critical)" />
          <Pill count={warningCount}  label="warnings" color="var(--warning)"  />
          <Pill count={infoCount}     label="info"     color="var(--info)"     />
        </div>
      </div>
    </div>
  )
}

function Pill({ count, label, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <span style={{
        background: color + '22',
        color,
        borderRadius: '4px',
        padding: '1px 8px',
        fontSize: '0.8rem',
        fontWeight: 600,
        minWidth: '30px',
        textAlign: 'center',
      }}>{count}</span>
      <span style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>{label}</span>
    </div>
  )
}
