import { useState, useRef } from 'react'
import FileDropzone from './components/FileDropzone'
import ProgressStream from './components/ProgressStream'
import ReportPanel from './components/ReportPanel'

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export default function App() {
  const [phase, setPhase]       = useState('idle')
  const [messages, setMessages] = useState([])
  const [report, setReport]     = useState(null)
  const [errMsg, setErrMsg]     = useState('')
  const abortRef = useRef(null)

  const handleFile = async (file) => {
    setPhase('running')
    setMessages([])
    setReport(null)
    setErrMsg('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const resp = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        body: formData,
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }))
        throw new Error(err.detail || 'Server error')
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          try {
            const event = JSON.parse(raw)
            if (event.type === 'progress') {
              setMessages(prev => [...prev, event.message])
            } else if (event.type === 'report') {
              setReport(event.data)
              setPhase('done')
            } else if (event.type === 'error') {
              throw new Error(event.message)
            }
          } catch (parseErr) {
            // ignore malformed SSE line
          }
        }
      }
    } catch (err) {
      setErrMsg(err.message)
      setPhase('error')
    }
  }

  const reset = () => {
    setPhase('idle')
    setMessages([])
    setReport(null)
    setErrMsg('')
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>

      {/* ── Header ── */}
      <header style={{
        borderBottom: '1px solid var(--border)',
        padding: '0.85rem 2rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        background: 'var(--surface)',
      }}>
        {/* Logo mark — a small green pulse ring */}
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
          <circle cx="11" cy="11" r="4" fill="var(--accent)" />
          <circle cx="11" cy="11" r="8" stroke="var(--accent)" strokeWidth="1.5" strokeOpacity="0.4" />
          <circle cx="11" cy="11" r="10.5" stroke="var(--accent)" strokeWidth="1" strokeOpacity="0.15" />
        </svg>
        <span style={{ fontWeight: 600, fontSize: '1rem', letterSpacing: '-0.02em', color: 'var(--text)' }}>
          DataPulse
        </span>
        <span style={{ color: 'var(--muted)', fontSize: '0.78rem', marginLeft: '0.15rem' }}>
          Data Quality Analysis
        </span>
      </header>

      {/* ── Main ── */}
      <main style={{
        flex: 1,
        maxWidth: '840px',
        width: '100%',
        margin: '0 auto',
        padding: '2rem 1.5rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
      }}>

        {/* Idle */}
        {phase === 'idle' && (
          <>
            <div style={{ textAlign: 'center', padding: '1.5rem 0 0.75rem' }}>
              <h1 style={{
                fontWeight: 600,
                fontSize: '1.45rem',
                margin: '0 0 0.45rem',
                letterSpacing: '-0.025em',
                color: 'var(--text)',
              }}>
                Drop your dataset, get a full quality report
              </h1>
              <p style={{ color: 'var(--muted)', margin: 0, fontSize: '0.875rem' }}>
                Powered by a LangGraph agent · schema · outliers · distributions · duplicates · correlations
              </p>
            </div>
            <FileDropzone onFileSelected={handleFile} disabled={false} />
          </>
        )}

        {/* Running / Error */}
        {(phase === 'running' || phase === 'error') && (
          <>
            <h2 style={{ margin: 0, fontWeight: 500, fontSize: '0.9rem', color: 'var(--muted)', letterSpacing: '0.04em' }}>
              {phase === 'running' ? '● ANALYZING' : '✕ ANALYSIS FAILED'}
            </h2>
            <ProgressStream messages={messages} />
            {phase === 'error' && (
              <div style={{
                background: 'rgba(248,113,113,0.07)',
                border: '1px solid rgba(248,113,113,0.25)',
                borderLeft: '3px solid var(--critical)',
                borderRadius: '8px',
                padding: '1rem 1.25rem',
                color: 'var(--critical)',
              }}>
                <strong>Error:</strong> {errMsg}
                <br />
                <button onClick={reset} style={{
                  marginTop: '0.75rem', background: 'none',
                  border: '1px solid var(--critical)',
                  borderRadius: '6px', color: 'var(--critical)',
                  padding: '0.35rem 0.9rem',
                  cursor: 'pointer', fontSize: '0.82rem',
                }}>Try again</button>
              </div>
            )}
          </>
        )}

        {/* Done */}
        {phase === 'done' && report && (
          <>
            <ProgressStream messages={messages} />
            <ReportPanel report={report} onReset={reset} />
          </>
        )}

      </main>
    </div>
  )
}
