import { useState, useEffect, useRef } from 'react'
import { Panel, PanelHeader } from '../ui'
import {
  Link, Upload, HardDrive, AlertCircle, Film, ArrowRight, FolderOpen,
  Check, Loader2, CircleDot, ScanSearch, Scissors, Sparkles, Tag,
} from 'lucide-react'

const STEP_ICONS = {
  download: Film,
  transcribe: CircleDot,
  detect: ScanSearch,
  cut: Scissors,
  render: Sparkles,
}

const TAG_OPTIONS = [
  { value: 'engraçado',     emoji: '😂', color: 'yellow' },
  { value: 'drama',          emoji: '🎭', color: 'red' },
  { value: 'reflexão',       emoji: '💭', color: 'blue' },
  { value: 'dica',           emoji: '💡', color: 'green' },
  { value: 'polêmica',       emoji: '🔥', color: 'orange' },
  { value: 'storytelling',   emoji: '📖', color: 'purple' },
  { value: 'emocional',      emoji: '❤️', color: 'pink' },
  { value: 'viral',          emoji: '🚀', color: 'cyan' },
]

const TAG_ACTIVE_STYLES = {
  yellow:  'bg-yellow-500/20 text-yellow-400 border-yellow-500/40',
  red:     'bg-red-500/20 text-red-400 border-red-500/40',
  blue:    'bg-blue-500/20 text-blue-400 border-blue-500/40',
  green:   'bg-green-500/20 text-green-400 border-green-500/40',
  orange:  'bg-orange-500/20 text-orange-400 border-orange-500/40',
  purple:  'bg-purple-500/20 text-purple-400 border-purple-500/40',
  pink:    'bg-pink-500/20 text-pink-400 border-pink-500/40',
  cyan:    'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
}

export default function ProcessingPanel({ onStart, onUpload, processing, progress, step, error, pipeline, onCancel }) {
  const urlRef = useRef('')
  const fileRef = useRef(null)
  const [localVideos, setLocalVideos] = useState([])
  const [selectedVideo, setSelectedVideo] = useState('')
  const [activeTab, setActiveTab] = useState('url')
  const [dragOver, setDragOver] = useState(false)
  const [selectedTag, setSelectedTag] = useState(null)

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
    onStart(url, null, selectedTag)
  }

  function handleLocalProcess() {
    if (!selectedVideo) return
    onStart(null, selectedVideo, selectedTag)
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (file) onUpload(file, selectedTag)
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) onUpload(file, selectedTag)
  }

  const inputClass = 'w-full px-3 py-2 bg-bg-elevated border border-border rounded-md text-xs text-text outline-none focus:border-accent focus:ring-[3px] focus:ring-accent/[0.08] transition-all placeholder:text-text-muted disabled:opacity-40'

  const btnPrimary = 'flex items-center justify-center gap-1.5 px-3.5 py-[7px] bg-accent text-white rounded-md text-xs font-medium hover:bg-accent-hover hover:shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-all border-none disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none'

  return (
    <Panel>
      <PanelHeader>
        <div className="flex items-center gap-2">
          <Film size={16} className="text-accent shrink-0" />
          <span className="text-xs font-semibold text-text" style={{ letterSpacing: '0.3px' }}>Importar Video</span>
        </div>
      </PanelHeader>

      <div className="px-4 py-3.5 flex flex-col gap-3">
        {/* Tab switcher */}
        <div className="flex gap-0.5 bg-bg-elevated rounded-md p-0.5 mb-1">
          {[
            { key: 'url', label: 'URL', icon: Link },
            { key: 'upload', label: 'Upload', icon: Upload },
            { key: 'local', label: 'Local', icon: HardDrive },
          ].map(t => (
            <button
              key={t.key}
              className={`flex-1 flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded text-[11px] font-medium transition-all ${activeTab === t.key ? 'bg-accent text-white shadow-[0_1px_4px_rgba(0,0,0,0.3)]' : 'bg-transparent text-text-secondary hover:text-text border-none'}`}
              onClick={() => setActiveTab(t.key)}
            >
              <t.icon size={13} /> {t.label}
            </button>
          ))}
        </div>

        {/* Tag selector */}
        <div className="mb-1">
          <label className="flex items-center gap-1 text-[10px] font-medium text-text-secondary mb-1.5" style={{ letterSpacing: '0.3px' }}>
            <Tag size={12} className="opacity-50" /> Categoria (opcional)
          </label>
          <div className="flex flex-wrap gap-1">
            {TAG_OPTIONS.map(t => (
              <button
                key={t.value}
                disabled={processing}
                className={`inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-md border font-medium transition-all ${selectedTag === t.value ? TAG_ACTIVE_STYLES[t.color] : 'bg-bg-elevated text-text-muted border-border hover:text-text hover:border-border-light'}`}
                onClick={() => setSelectedTag(selectedTag === t.value ? null : t.value)}
              >
                <span>{t.emoji}</span>
                <span>{t.value}</span>
              </button>
            ))}
          </div>
        </div>

        {/* URL tab */}
        {activeTab === 'url' && (
          <div style={{ animation: 'fade-in 0.2s ease forwards' }}>
            <label className="flex items-center gap-1 text-[10px] font-medium text-text-secondary mb-1.5" style={{ letterSpacing: '0.3px' }}>URL da Live (YouTube, Twitch, etc)</label>
            <div className="flex gap-1.5">
              <input
                type="text"
                placeholder="https://www.youtube.com/watch?v=..."
                onChange={(e) => urlRef.current = e.target.value}
                disabled={processing}
                onKeyDown={(e) => e.key === 'Enter' && handleSubmitUrl()}
                className="flex-1 min-w-0 px-3 py-2 bg-bg-elevated border border-border rounded-md text-xs text-text outline-none focus:border-accent focus:ring-[3px] focus:ring-accent/[0.08] transition-all placeholder:text-text-muted disabled:opacity-40"
              />
              <button
                className="flex items-center justify-center gap-1.5 px-3.5 py-2 bg-accent text-white rounded-md text-xs font-medium hover:bg-accent-hover hover:shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-all border-none shrink-0 disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none"
                onClick={handleSubmitUrl}
                disabled={processing}
              >
                <ArrowRight size={14} />
              </button>
            </div>
          </div>
        )}

        {/* Upload tab */}
        {activeTab === 'upload' && (
          <div style={{ animation: 'fade-in 0.2s ease forwards' }}>
            <div
              className={`flex flex-col items-center text-center gap-0 py-6 px-4 border-2 border-dashed rounded-[10px] cursor-pointer transition-all ${dragOver ? 'border-accent bg-accent/[0.08]' : 'border-border hover:border-accent hover:bg-accent/[0.08]'}`}
              onClick={() => fileRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
            >
              <Upload size={32} className="text-text-muted mb-2 block" />
              <div className="text-[13px] font-medium text-text-secondary mb-0.5">Arraste um video ou clique para selecionar</div>
              <div className="text-[11px] text-text-muted">MP4, MOV, AVI, MKV</div>
              <input ref={fileRef} type="file" accept="video/*" onChange={handleFileChange} className="hidden" />
            </div>
          </div>
        )}

        {/* Local tab */}
        {activeTab === 'local' && (
          <div style={{ animation: 'fade-in 0.2s ease forwards' }}>
            <label className="flex items-center gap-1 text-[10px] font-medium text-text-secondary mb-1.5" style={{ letterSpacing: '0.3px' }}>
              <FolderOpen size={12} className="opacity-50" /> Videos no servidor
            </label>
            <select
              className="w-full px-2.5 py-[7px] bg-bg-elevated border border-border rounded-md text-xs text-text outline-none focus:border-accent focus:ring-[3px] focus:ring-accent/[0.08] cursor-pointer transition-all mb-3 disabled:opacity-40"
              style={{ WebkitAppearance: 'none' }}
              value={selectedVideo}
              onChange={(e) => setSelectedVideo(e.target.value)}
              disabled={processing}
            >
              <option value="">Selecione um video...</option>
              {localVideos.map((v) => (
                <option key={v.arquivo} value={v.caminho}>{v.arquivo} ({v.tamanho_mb} MB)</option>
              ))}
            </select>
            <button
              className="flex items-center justify-center gap-1.5 w-full px-3.5 py-2 bg-accent text-white rounded-md text-xs font-medium hover:bg-accent-hover hover:shadow-[0_0_16px_rgba(124,58,237,0.2)] transition-all border-none disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none"
              onClick={handleLocalProcess}
              disabled={processing || !selectedVideo}
            >
              Processar Video
            </button>
          </div>
        )}

        {/* Progress + Pipeline */}
        {(processing || progress > 0) && (
          <div className="flex flex-col gap-2.5 mt-1">
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs text-text-secondary">{step}</span>
                  <span className="text-xs font-semibold text-accent-light" style={{ fontVariantNumeric: 'tabular-nums' }}>{Math.round(progress)}%</span>
                </div>
                <div className="w-full h-1 bg-bg-elevated rounded-sm overflow-hidden">
                  <div className="h-full bg-accent rounded-sm transition-all duration-300" style={{ width: `${progress}%` }} />
                </div>
              </div>
              {processing && (
                <button
                  className="flex items-center gap-1 px-2 py-[3px] bg-danger/10 text-danger border border-danger/20 rounded-md text-[11px] hover:bg-danger hover:text-white transition-all shrink-0"
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
                      s.status === 'active' ? 'text-accent-light bg-accent/[0.08]' :
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

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 px-3 py-2 bg-danger/10 border border-danger/20 rounded-md text-xs text-danger">
            <AlertCircle size={14} className="shrink-0" />
            {error}
          </div>
        )}
      </div>
    </Panel>
  )
}
