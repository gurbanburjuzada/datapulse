import { useState, useRef } from 'react'

export default function FileDropzone({ onFileSelected, disabled }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) validate(file)
  }

  const handleChange = (e) => {
    const file = e.target.files[0]
    if (file) validate(file)
  }

  const validate = (file) => {
    const allowed = ['.csv', '.xlsx', '.xls']
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!allowed.includes(ext)) {
      alert(`Unsupported file type: ${ext}. Please upload a CSV or Excel file.`)
      return
    }
    onFileSelected(file)
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      style={{
        border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: '14px',
        padding: '3.5rem 2rem',
        textAlign: 'center',
        background: dragging
          ? 'rgba(74, 222, 128, 0.04)'
          : 'var(--surface)',
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? 'none' : 'auto',
        cursor: 'pointer',
        userSelect: 'none',
        transition: 'border-color 0.18s, background 0.18s',
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        onChange={handleChange}
        style={{ display: 'none' }}
      />

      {/* Icon — green pulse dot instead of emoji */}
      <div style={{ marginBottom: '1.25rem', display: 'flex', justifyContent: 'center' }}>
        <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
          <rect width="44" height="44" rx="10" fill="var(--surface2)" />
          <rect x="13" y="12" width="18" height="22" rx="2" stroke="var(--accent)" strokeWidth="1.5" fill="none" />
          <line x1="17" y1="18" x2="27" y2="18" stroke="var(--accent)" strokeWidth="1.2" strokeOpacity="0.6" />
          <line x1="17" y1="22" x2="27" y2="22" stroke="var(--accent)" strokeWidth="1.2" strokeOpacity="0.6" />
          <line x1="17" y1="26" x2="23" y2="26" stroke="var(--accent)" strokeWidth="1.2" strokeOpacity="0.6" />
        </svg>
      </div>

      <p style={{
        color: dragging ? 'var(--accent)' : 'var(--text)',
        fontWeight: 500,
        fontSize: '0.95rem',
        marginBottom: '0.4rem',
        transition: 'color 0.18s',
      }}>
        {dragging ? 'Release to analyze' : 'Drop your dataset here'}
      </p>
      <p style={{ color: 'var(--muted)', fontSize: '0.82rem', margin: '0 0 1.25rem' }}>
        CSV, XLSX or XLS · up to 50 MB
      </p>
      <span style={{
        display: 'inline-block',
        background: 'var(--surface2)',
        border: '1px solid var(--border)',
        borderRadius: '6px',
        color: 'var(--muted)',
        padding: '0.3rem 0.9rem',
        fontSize: '0.8rem',
      }}>
        or click to browse
      </span>
    </div>
  )
}
