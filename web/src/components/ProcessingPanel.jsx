import { useState, useEffect, useRef } from 'react'
import {
  Link, Upload, HardDrive, AlertCircle, Film, ArrowRight, FolderOpen,
  Check, Loader2, CircleDot, ScanSearch, Scissors, Sparkles,
} from 'lucide-react'

const STEP_ICONS = {
  download: Film,
  transcribe: CircleDot,
  detect: ScanSearch,
  cut: Scissors,
  render: Sparkles,
}

export default function ProcessingPanel({ onStart, onUpload, processing, progress, step, error, pipeline, onCancel }) {
  const urlRef = useRef('')
  const fileRef = useRef(null)
  const [localVideos, setLocalVideos] = useState([])
  const [selectedVideo, setSelectedVideo] = useState('')
  const [activeTab, setActiveTab] = useState('url')
  const [dragOver, setDragOver] = useState(false)

  useEffect(() => { fetchLocalVideos() }, [])

  async function fetchLocalVideos() {
    try {
      const res = await fetch('/api/videos')
      const data = await res.json()
      setLocalVideos(data.videos || [])
    } catch {}
  }

  function handleSubmitUrl() {
    const url = urlRef.current?.trim()
    if (!url) return
    onStart(url)
  }

  function handleLocalProcess() {
    if (!selectedVideo) return
    onStart(null, selectedVideo)
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (file) onUpload(file)
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) onUpload(file)
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-header-left">
          <Film className="panel-icon" />
          <span className="panel-title">Importar Video</span>
        </div>
      </div>

      <div className="panel-body">
        <div className="tabs">
          <button className={`tab ${activeTab === 'url' ? 'active' : ''}`} onClick={() => setActiveTab('url')}>
            <Link className="tab-icon" /> URL
          </button>
          <button className={`tab ${activeTab === 'upload' ? 'active' : ''}`} onClick={() => setActiveTab('upload')}>
            <Upload className="tab-icon" /> Upload
          </button>
          <button className={`tab ${activeTab === 'local' ? 'active' : ''}`} onClick={() => setActiveTab('local')}>
            <HardDrive className="tab-icon" /> Local
          </button>
        </div>

        {activeTab === 'url' && (
          <div className="fade-in">
            <div className="form-group">
              <label className="form-label">URL da Live (YouTube, Twitch, etc)</label>
              <div style={{ display: 'flex', gap: 6 }}>
                <input className="form-input" type="text"
                  placeholder="https://www.youtube.com/watch?v=..."
                  onChange={(e) => urlRef.current = e.target.value}
                  disabled={processing}
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmitUrl()}
                  style={{ flex: 1, minWidth: 0 }} />
                <button className="btn btn-primary" onClick={handleSubmitUrl} disabled={processing}>
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'upload' && (
          <div className="fade-in">
            <div className="upload-zone"
              style={dragOver ? { borderColor: 'var(--accent)', background: 'var(--accent-bg)' } : {}}
              onClick={() => fileRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}>
              <Upload className="upload-zone-icon" />
              <div className="upload-zone-title">Arraste um video ou clique para selecionar</div>
              <div className="upload-zone-hint">MP4, MOV, AVI, MKV</div>
              <input ref={fileRef} type="file" accept="video/*" onChange={handleFileChange} style={{ display: 'none' }} />
            </div>
          </div>
        )}

        {activeTab === 'local' && (
          <div className="fade-in">
            <div className="form-group">
              <label className="form-label"><FolderOpen className="form-label-icon" /> Videos no servidor</label>
              <select className="form-select" value={selectedVideo}
                onChange={(e) => setSelectedVideo(e.target.value)} disabled={processing}>
                <option value="">Selecione um video...</option>
                {localVideos.map((v) => (
                  <option key={v.arquivo} value={v.caminho}>{v.arquivo} ({v.tamanho_mb} MB)</option>
                ))}
              </select>
            </div>
            <button className="btn btn-primary" onClick={handleLocalProcess}
              disabled={processing || !selectedVideo} style={{ width: '100%' }}>
              Processar Video
            </button>
          </div>
        )}

        {(processing || progress > 0) && (
          <div className="progress-section">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <div className="progress-header">
                  <span className="progress-step">{step}</span>
                  <span className="progress-pct">{Math.round(progress)}%</span>
                </div>
                <div className="progress-bar-bg">
                  <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
                </div>
              </div>
              {processing && (
                <button className="cancel-btn" onClick={onCancel}>
                  Cancelar
                </button>
              )}
            </div>

            <div className="pipeline-steps">
              {pipeline.map((s, i) => {
                const Icon = STEP_ICONS[s.key] || CircleDot
                return (
                  <span key={s.key} style={{ display: 'contents' }}>
                    <div className={`pipeline-step ${s.status}`}>
                      <Icon className="pipeline-step-icon" />
                      {s.label}
                    </div>
                    {i < pipeline.length - 1 && (
                      <div className={`pipeline-connector ${s.status === 'done' ? 'done' : ''}`} />
                    )}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {error && (
          <div className="error-msg">
            <AlertCircle className="error-msg-icon" />
            {error}
          </div>
        )}
      </div>
    </div>
  )
}
