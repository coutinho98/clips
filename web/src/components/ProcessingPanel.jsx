import { useState, useEffect, useRef } from 'react'
import { Panel, PanelHeader, Button } from '../ui'
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
    <Panel>
      <PanelHeader>
        <div className="flex items-center gap-2">
          <Film size={14} className="text-accent-light" />
          <span className="text-xs font-semibold text-text">Importar Video</span>
        </div>
      </PanelHeader>

      <div className="p-4 flex flex-col gap-3">
        <div className="flex gap-1 bg-bg-elevated rounded-lg p-0.5">
          {[
            { key: 'url', label: 'URL', icon: Link },
            { key: 'upload', label: 'Upload', icon: Upload },
            { key: 'local', label: 'Local', icon: HardDrive },
          ].map(t => (
            <button
              key={t.key}
              className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${activeTab === t.key ? 'bg-accent text-white' : 'text-text-secondary hover:text-text'}`}
              onClick={() => setActiveTab(t.key)}
            >
              <t.icon size={13} /> {t.label}
            </button>
          ))}
        </div>

        {activeTab === 'url' && (
          <div style={{ animation: 'fade-in 0.2s ease forwards' }}>
            <label className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary mb-1.5">URL da Live (YouTube, Twitch, etc)</label>
            <div className="flex gap-1.5">
              <input
                type="text"
                placeholder="https://www.youtube.com/watch?v=..."
                onChange={(e) => urlRef.current = e.target.value}
                disabled={processing}
                onKeyDown={(e) => e.key === 'Enter' && handleSubmitUrl()}
                className="flex-1 min-w-0 px-2.5 py-1.5 bg-bg-elevated border border-border rounded-md text-xs text-text outline-none focus:border-accent transition-colors"
              />
              <Button variant="primary" onClick={handleSubmitUrl} disabled={processing}>
                <ArrowRight size={14} />
              </Button>
            </div>
          </div>
        )}

        {activeTab === 'upload' && (
          <div style={{ animation: 'fade-in 0.2s ease forwards' }}>
            <div
              className={`flex flex-col items-center justify-center gap-2 py-8 border-2 border-dashed rounded-lg cursor-pointer transition-all ${dragOver ? 'border-accent bg-accent/10' : 'border-border-light hover:border-accent/50 hover:bg-bg-hover'}`}
              onClick={() => fileRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
            >
              <Upload size={28} className="text-accent-light" />
              <div className="text-xs font-medium text-text">Arraste um video ou clique para selecionar</div>
              <div className="text-[10px] text-text-muted">MP4, MOV, AVI, MKV</div>
              <input ref={fileRef} type="file" accept="video/*" onChange={handleFileChange} className="hidden" />
            </div>
          </div>
        )}

        {activeTab === 'local' && (
          <div style={{ animation: 'fade-in 0.2s ease forwards' }}>
            <label className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary mb-1.5">
              <FolderOpen size={11} className="text-text-muted" /> Videos no servidor
            </label>
            <select
              className="w-full px-2.5 py-1.5 bg-bg-elevated border border-border rounded-md text-xs text-text outline-none focus:border-accent cursor-pointer transition-colors mb-2"
              value={selectedVideo}
              onChange={(e) => setSelectedVideo(e.target.value)}
              disabled={processing}
            >
              <option value="">Selecione um video...</option>
              {localVideos.map((v) => (
                <option key={v.arquivo} value={v.caminho}>{v.arquivo} ({v.tamanho_mb} MB)</option>
              ))}
            </select>
            <Button variant="primary" onClick={handleLocalProcess} disabled={processing || !selectedVideo} className="w-full">
              Processar Video
            </Button>
          </div>
        )}

        {(processing || progress > 0) && (
          <div className="flex flex-col gap-2.5 pt-1">
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-text-secondary">{step}</span>
                  <span className="text-[11px] font-semibold text-accent-light">{Math.round(progress)}%</span>
                </div>
                <div className="h-1.5 bg-bg-elevated rounded-full overflow-hidden">
                  <div className="h-full bg-accent rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
                </div>
              </div>
              {processing && (
                <button
                  className="px-2.5 py-1.5 text-[11px] text-danger bg-danger/10 border border-danger/30 rounded-md hover:bg-danger/20 transition-all shrink-0"
                  onClick={onCancel}
                >
                  Cancelar
                </button>
              )}
            </div>

            <div className="flex items-center gap-1 flex-wrap">
              {pipeline.map((s, i) => {
                const Icon = STEP_ICONS[s.key] || CircleDot
                return (
                  <span key={s.key} className="flex items-center gap-1">
                    <div className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium transition-all ${
                      s.status === 'done' ? 'text-success bg-success/10' :
                      s.status === 'active' ? 'text-accent-light bg-accent/10' :
                      'text-text-muted bg-bg-elevated'
                    }`}>
                      <Icon size={11} />
                      {s.label}
                      {s.status === 'done' && <Check size={10} />}
                      {s.status === 'active' && <Loader2 size={10} className="animate-spin" />}
                    </div>
                    {i < pipeline.length - 1 && (
                      <div className={`w-3 h-px ${s.status === 'done' ? 'bg-success/40' : 'bg-border'}`} />
                    )}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 px-3 py-2 bg-danger/10 border border-danger/30 rounded-md text-xs text-danger">
            <AlertCircle size={14} className="shrink-0" />
            {error}
          </div>
        )}
      </div>
    </Panel>
  )
}
