import { useState } from 'react'
import QualityScore from './QualityScore'

// ── Severity helpers ──────────────────────────────────────────────────────────

const SEV_ORDER = { critical: 0, warning: 1, info: 2 }

const SEV_COLOR = {
  critical: 'var(--critical)',
  warning:  'var(--warning)',
  info:     'var(--info)',
}

const SEV_BG = {
  critical: 'var(--critical-bg)',
  warning:  'var(--warning-bg)',
  info:     'var(--info-bg)',
}

// ── Grouping helper ───────────────────────────────────────────────────────────

/**
 * Groups findings by exact recommendation string.
 * Returns an array of group objects sorted critical → warning → info.
 * Within each group, affected columns are sorted alphabetically.
 */
function groupFindings(findings) {
  const map = new Map()

  for (const f of findings) {
    const key = f.recommendation
    if (!map.has(key)) {
      map.set(key, {
        recommendation: f.recommendation,
        severity: f.severity,          // will be upgraded to highest
        title: f.title,                // fallback title (first seen)
        items: [],
      })
    }
    const group = map.get(key)

    // Upgrade severity to highest in group
    if (SEV_ORDER[f.severity] < SEV_ORDER[group.severity]) {
      group.severity = f.severity
    }

    group.items.push({
      column: f.column || null,
      detail: f.detail,
      title:  f.title,
    })
  }

  // Sort items within each group alphabetically by column name
  for (const group of map.values()) {
    group.items.sort((a, b) => (a.column || '').localeCompare(b.column || ''))
  }

  // Sort groups: critical → warning → info
  return [...map.values()].sort(
    (a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]
  )
}

// ── ReportPanel ───────────────────────────────────────────────────────────────

export default function ReportPanel({ report, onReset }) {
  const [activeTab, setActiveTab] = useState('findings')

  const tabs = [
    { id: 'findings',  label: `Findings (${report.findings.length})` },
    { id: 'schema',    label: 'Schema' },
    { id: 'heatmap',   label: 'Correlation' },
    { id: 'summary',   label: 'AI Summary' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>

      {/* ── Header row ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ margin: 0, fontWeight: 600, fontSize: '1.05rem', letterSpacing: '-0.01em' }}>
            {report.file_name}
          </h2>
          <p style={{ margin: '2px 0 0', color: 'var(--muted)', fontSize: '0.82rem' }}>
            {report.row_count.toLocaleString()} rows · {report.col_count} columns
          </p>
        </div>
        <button
          onClick={onReset}
          style={{
            background: 'var(--surface2)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            color: 'var(--muted)',
            padding: '0.4rem 1rem',
            cursor: 'pointer',
            fontSize: '0.82rem',
            transition: 'border-color 0.15s, color 0.15s',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = 'var(--accent)'
            e.currentTarget.style.color = 'var(--accent)'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.color = 'var(--muted)'
          }}
        >
          Analyze another file
        </button>
      </div>

      {/* ── Score card — pass full findings array for accurate counts ── */}
      <QualityScore score={report.quality_score} findings={report.findings} />

      {/* ── Tabs ── */}
      <div style={{
        display: 'flex',
        gap: '2px',
        borderBottom: '1px solid var(--border)',
      }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '0.5rem 1rem 0.55rem',
              fontSize: '0.85rem',
              fontWeight: activeTab === tab.id ? 500 : 400,
              color: activeTab === tab.id ? 'var(--accent)' : 'var(--muted)',
              borderBottom: activeTab === tab.id
                ? '2px solid var(--accent)'
                : '2px solid transparent',
              marginBottom: '-1px',
              transition: 'color 0.15s',
            }}
          >{tab.label}</button>
        ))}
      </div>

      {/* ── Tab content ── */}
      {activeTab === 'findings' && <FindingsTab findings={report.findings} />}
      {activeTab === 'schema'   && <SchemaTab columns={report.columns} />}
      {activeTab === 'heatmap'  && <HeatmapTab data={report.heatmap_data} />}
      {activeTab === 'summary'  && <SummaryTab summary={report.llm_summary} />}
    </div>
  )
}

// ── Findings Tab ──────────────────────────────────────────────────────────────

function FindingsTab({ findings }) {
  if (findings.length === 0) {
    return (
      <p style={{ color: 'var(--muted)', textAlign: 'center', padding: '2.5rem' }}>
        No issues found — clean dataset ✓
      </p>
    )
  }

  const groups = groupFindings(findings)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
      {groups.map((group, i) => (
        <GroupCard key={i} group={group} />
      ))}
    </div>
  )
}

function GroupCard({ group }) {
  const [expanded, setExpanded] = useState(true)
  const isMulti = group.items.length > 1
  const sev = group.severity
  const color = SEV_COLOR[sev]
  const bg    = SEV_BG[sev]

  // Derive a clean group title
  const groupTitle = isMulti
    ? (() => {
        // Strip trailing column name from first item's title to get the issue type
        const base = group.items[0].title
          .replace(/'[^']*'/g, '')          // remove quoted column names
          .replace(/\s+in\s*$/, '')          // remove trailing "in"
          .replace(/\s+for\s*$/, '')
          .trim()
        return `${base} (${group.items.length} columns)`
      })()
    : group.items[0].title

  return (
    <div style={{
      background: bg,
      border: `1px solid ${color}28`,
      borderLeft: `3px solid ${color}`,
      borderRadius: '8px',
      padding: '0.75rem 1rem',
    }}>
      {/* ── Card header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.3rem' }}>
        <span style={{
          fontSize: '0.67rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          color,
          letterSpacing: '0.06em',
        }}>{sev}</span>

        {/* Single-finding column badge */}
        {!isMulti && group.items[0].column && (
          <span style={{
            fontFamily: 'monospace',
            fontSize: '0.72rem',
            color: 'var(--muted)',
            background: 'var(--surface2)',
            padding: '1px 6px',
            borderRadius: '4px',
          }}>{group.items[0].column}</span>
        )}

        {/* Expand/collapse for multi-column groups */}
        {isMulti && (
          <button
            onClick={() => setExpanded(v => !v)}
            style={{
              marginLeft: 'auto',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--muted)',
              fontSize: '0.75rem',
              padding: '0 2px',
            }}
          >
            {expanded ? '▾ collapse' : '▸ expand'}
          </button>
        )}
      </div>

      {/* ── Title ── */}
      <div style={{
        fontWeight: 500,
        fontSize: '0.88rem',
        marginBottom: isMulti && expanded ? '0.5rem' : '0.25rem',
      }}>
        {groupTitle}
      </div>

      {/* ── Single finding detail ── */}
      {!isMulti && (
        <div style={{ color: 'var(--muted)', fontSize: '0.8rem', marginBottom: '0.3rem' }}>
          {group.items[0].detail}
        </div>
      )}

      {/* ── Multi-finding column list ── */}
      {isMulti && expanded && (
        <div style={{
          maxHeight: '160px',
          overflowY: 'auto',
          marginBottom: '0.45rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '2px',
        }}>
          {group.items.map((item, j) => (
            <div key={j} style={{
              display: 'flex',
              gap: '0.5rem',
              fontSize: '0.78rem',
              color: 'var(--muted)',
              paddingLeft: '0.1rem',
            }}>
              <span style={{
                fontFamily: 'monospace',
                fontSize: '0.72rem',
                color: 'var(--text)',
                flexShrink: 0,
                minWidth: '120px',
              }}>
                {item.column || '—'}
              </span>
              <span style={{ opacity: 0.8 }}>{item.detail}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Shared recommendation ── */}
      <div style={{
        color: 'var(--text)',
        fontSize: '0.79rem',
        fontStyle: 'italic',
        opacity: 0.75,
        borderTop: isMulti ? `1px solid ${color}18` : 'none',
        paddingTop: isMulti ? '0.45rem' : 0,
        marginTop: isMulti ? '0.1rem' : 0,
      }}>
        💡 {group.recommendation}
      </div>
    </div>
  )
}

// ── Schema Tab ────────────────────────────────────────────────────────────────

function SchemaTab({ columns }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            {['Column', 'Type', 'Nulls', 'Unique', 'Sample values'].map(h => (
              <th key={h} style={{
                padding: '0.45rem 0.75rem',
                textAlign: 'left',
                color: 'var(--muted)',
                fontWeight: 500,
                fontSize: '0.75rem',
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {columns.map((col, i) => (
            <tr key={i} style={{ borderBottom: `1px solid ${i % 2 === 0 ? 'var(--border)18' : 'transparent'}` }}>
              <td style={{
                padding: '0.45rem 0.75rem',
                fontFamily: 'monospace',
                fontSize: '0.75rem',
                color: 'var(--accent)',
              }}>
                {col.name}
              </td>
              <td style={{
                padding: '0.45rem 0.75rem',
                color: 'var(--muted)',
                fontFamily: 'monospace',
                fontSize: '0.72rem',
              }}>
                {col.dtype}
              </td>
              <td style={{ padding: '0.45rem 0.75rem' }}>
                <span style={{ color: col.null_pct > 10 ? 'var(--warning)' : 'var(--muted)' }}>
                  {col.null_pct.toFixed(1)}%
                </span>
              </td>
              <td style={{ padding: '0.45rem 0.75rem', color: 'var(--muted)' }}>
                {col.unique_count.toLocaleString()}
              </td>
              <td style={{
                padding: '0.45rem 0.75rem',
                color: 'var(--muted)',
                fontFamily: 'monospace',
                fontSize: '0.72rem',
              }}>
                {col.sample_values.slice(0, 3).join(', ')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Heatmap Tab ───────────────────────────────────────────────────────────────

function HeatmapTab({ data }) {
  if (!data?.columns?.length) {
    return (
      <p style={{ color: 'var(--muted)', textAlign: 'center', padding: '2rem' }}>
        No numeric columns available for correlation.
      </p>
    )
  }

  const { columns, matrix } = data

  const cellColor = (v) => {
    if (v === null) return 'var(--surface2)'
    const abs = Math.abs(v)
    if (v === 1)    return 'rgba(74,222,128,0.25)'
    if (abs > 0.85) return v > 0 ? 'rgba(74,222,128,0.55)' : 'rgba(248,113,113,0.55)'
    if (abs > 0.5)  return v > 0 ? 'rgba(74,222,128,0.3)'  : 'rgba(248,113,113,0.3)'
    return `rgba(90,122,96,${abs * 0.35})`
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{
        borderCollapse: 'separate',
        borderSpacing: '2px',
        fontSize: '0.7rem',
        fontFamily: 'monospace',
      }}>
        <thead>
          <tr>
            <th style={{ padding: '3px 8px' }}></th>
            {columns.map(c => (
              <th key={c} style={{
                padding: '3px 6px',
                color: 'var(--muted)',
                fontWeight: 400,
                maxWidth: '68px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                fontSize: '0.67rem',
              }}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <td style={{
                padding: '3px 10px 3px 4px',
                color: 'var(--muted)',
                whiteSpace: 'nowrap',
                fontSize: '0.67rem',
              }}>
                {columns[i]}
              </td>
              {row.map((val, j) => (
                <td key={j} style={{
                  padding: '4px 5px',
                  textAlign: 'center',
                  background: cellColor(val),
                  borderRadius: '3px',
                  color: Math.abs(val ?? 0) > 0.5 ? 'var(--text)' : 'var(--muted)',
                  minWidth: '46px',
                }}>
                  {val !== null ? val.toFixed(2) : '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── AI Summary Tab ────────────────────────────────────────────────────────────

function SummaryTab({ summary }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderLeft: '3px solid var(--accent)',
      borderRadius: '10px',
      padding: '1.25rem 1.5rem',
      lineHeight: 1.8,
      fontSize: '0.875rem',
      color: 'var(--text)',
    }}>
      <div style={{
        color: 'var(--accent)',
        fontSize: '0.68rem',
        marginBottom: '0.75rem',
        letterSpacing: '0.06em',
        opacity: 0.7,
      }}>
        AI SUMMARY · GPT-4o mini
      </div>
      <p style={{ margin: 0 }}>{summary}</p>
    </div>
  )
}
