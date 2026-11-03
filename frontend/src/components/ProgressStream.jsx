import { useEffect, useRef } from 'react'

export default function ProgressStream({ messages }) {
  const bottomRef = useRef()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '10px',
      padding: '0.85rem 1.1rem',
      fontFamily: '"JetBrains Mono", monospace',
      fontSize: '0.78rem',
      maxHeight: '200px',
      overflowY: 'auto',
      color: 'var(--text)',
      lineHeight: 1.5,
    }}>
      <div style={{
        color: 'var(--accent)',
        marginBottom: '0.45rem',
        fontSize: '0.67rem',
        letterSpacing: '0.08em',
        opacity: 0.7,
      }}>
        agent log
      </div>
      {messages.map((msg, i) => (
        <div key={i} style={{
          color: msg.startsWith('❌') ? 'var(--critical)' : 'var(--text)',
          paddingBottom: '1px',
        }}>
          <span style={{ color: 'var(--accent)', opacity: 0.45 }}>
            {String(i + 1).padStart(2, '0')}{' '}
          </span>
          {msg}
        </div>
      ))}
      {messages.length === 0 && (
        <div style={{ color: 'var(--muted)' }}>Waiting for file…</div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
