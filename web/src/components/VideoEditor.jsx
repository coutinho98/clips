import { useState, useEffect, useRef } from 'react'
import {
  ArrowLeft, Type, Crop, RotateCcw, Loader2,
  Palette, ZoomIn, ZoomOut, Maximize, Undo2, Redo2,
  Play, Pause, SkipBack, SkipForward, Move, MousePointer2,
} from 'lucide-react'
import LiveSubtitle from './LiveSubtitle'
import Timeline from './Timeline'

const SUBTITLE_STYLES = [
  { value: 'karaoke', label: 'Karaoke' },
  { value: 'neon', label: 'Neon' },
  { value: 'pop', label: 'Pop' },
  { value: 'slide', label: 'Slide' },
  { value: 'typewriter', label: 'Typewriter' },
  { value: 'rainbow', label: 'Rainbow' },
  { value: 'box', label: 'Box' },
  { value: 'sombra', label: 'Sombra' },
]

const FONT_OPTIONS = [
  { value: 'fira-sans',      label: 'Fira Sans',        css: "'Fira Sans', sans-serif",            weight: 600 },
  { value: 'fira-condensed', label: 'Fira Condensed',   css: "'Fira Sans Condensed', sans-serif",  weight: 700 },
  { value: 'open-sans',      label: 'Open Sans',        css: "'Open Sans', sans-serif",            weight: 700 },
  { value: 'montserrat',     label: 'Montserrat',       css: "'Montserrat', sans-serif",           weight: 800 },
  { value: 'poppins',        label: 'Poppins',          css: "'Poppins', sans-serif",              weight: 700 },
  { value: 'rubik',          label: 'Rubik',            css: "'Rubik', sans-serif",                weight: 700 },
  { value: 'raleway',        label: 'Raleway',          css: "'Raleway', sans-serif",              weight: 700 },
  { value: 'oswald',         label: 'Oswald',           css: "'Oswald', sans-serif",               weight: 700 },
  { value: 'teko',           label: 'Teko',             css: "'Teko', sans-serif",                 weight: 700 },
  { value: 'anton',          label: 'Anton',            css: "'Anton', sans-serif",                weight: 400 },
  { value: 'bebas-neue',     label: 'Bebas Neue',       css: "'Bebas Neue', sans-serif",           weight: 400 },
  { value: 'league-spartan', label: 'League Spartan',   css: "'League Spartan', sans-serif",       weight: 700 },
  { value: 'roboto-slab',    label: 'Roboto Slab',      css: "'Roboto Slab', serif",               weight: 700 },
]

export default function VideoEditor({ cut, config, onRerender, onClose, processing }) {
  const [editConfig, setEditConfig] = useState({
    font_size: config?.font_size || 52,
    text_margin_bottom: config?.text_margin_bottom || 180,
    subtitle_style: config?.subtitle_style || 'karaoke',
    font_family: config?.font_family || 'fira-sans',
    highlight_color: config?.highlight_color || '#FFFF32',
    base_color: config?.base_color || '#B4B4B4',
    crop_vertical: config?.crop_vertical ?? true,
  })
  const [history, setHistory] = useState([])
  const [historyIdx, setHistoryIdx] = useState(-1)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [isPlaying, setIsPlaying] = useState(false)
  const [zoom, setZoom] = useState(100)
  const [dragMode, setDragMode] = useState(false)
  const [meta, setMeta] = useState(null)
  const [videoDuration, setVideoDuration] = useState(0)
  const [videoSize, setVideoSize] = useState({ w: 0, h: 0 })
  const previewVideoRef = useRef(null)

  useEffect(() => {
    const initial = {
      font_size: config?.font_size || 52,
      text_margin_bottom: config?.text_margin_bottom || 180,
      subtitle_style: config?.subtitle_style || 'karaoke',
      font_family: config?.font_family || 'fira-sans',
      highlight_color: config?.highlight_color || '#FFFF32',
      base_color: config?.base_color || '#B4B4B4',
      crop_vertical: config?.crop_vertical ?? true,
    }
    setEditConfig(initial)
    setHistory([initial])
    setHistoryIdx(0)
  }, [cut?.cut_id])

  useEffect(() => {
    if (!cut?.cut_id) return
    fetch(`/api/cut/${encodeURIComponent(cut.cut_id)}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setMeta(d))
      .catch(() => {})
  }, [cut?.cut_id])

  function pushHistory(newConfig) {
    setHistory(prev => {
      const next = prev.slice(0, historyIdx + 1)
      next.push(newConfig)
      if (next.length > 50) next.shift()
      return next
    })
    setHistoryIdx(prev => Math.min(prev + 1, 49))
  }

  function handleChange(key, value) {
    const newConfig = { ...editConfig, [key]: value }
    setEditConfig(newConfig)
    pushHistory(newConfig)
  }

  function handleUndo() {
    if (historyIdx <= 0) return
    const newIdx = historyIdx - 1
    setHistoryIdx(newIdx)
    setEditConfig(history[newIdx])
  }

  function handleRedo() {
    if (historyIdx >= history.length - 1) return
    const newIdx = historyIdx + 1
    setHistoryIdx(newIdx)
    setEditConfig(history[newIdx])
  }

  function togglePlayPause() {
    const v = previewVideoRef.current
    if (!v) return
    if (v.paused) { v.play(); setIsPlaying(true) }
    else { v.pause(); setIsPlaying(false) }
  }

  function stepFrame(direction) {
    const v = previewVideoRef.current
    if (!v) return
    v.pause()
    setIsPlaying(false)
    v.currentTime = Math.max(0, v.currentTime + direction * (1 / 30))
  }

  function cycleSpeed() {
    const speeds = [0.5, 1, 1.5, 2]
    const idx = speeds.indexOf(playbackSpeed)
    const next = speeds[(idx + 1) % speeds.length]
    setPlaybackSpeed(next)
    if (previewVideoRef.current) previewVideoRef.current.playbackRate = next
  }

  const videoSrc = `/api/cuts/${encodeURIComponent(cut.arquivo)}`

  return (
    <div className="bg-bg-tertiary border border-border rounded-xl overflow-hidden flex flex-col h-full min-h-0" style={{ animation: 'slide-in-right 0.25s ease forwards' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1 border-b border-border shrink-0">
        <span className="text-[11px] font-semibold text-text truncate">Editor - {cut.titulo}</span>
        <div className="flex items-center gap-1 shrink-0">
          <button className="flex items-center justify-center w-7 h-7 rounded-md text-text-secondary hover:text-text hover:bg-bg-hover transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            onClick={handleUndo} disabled={historyIdx <= 0} title="Desfazer">
            <Undo2 size={12} />
          </button>
          <button className="flex items-center justify-center w-7 h-7 rounded-md text-text-secondary hover:text-text hover:bg-bg-hover transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            onClick={handleRedo} disabled={historyIdx >= history.length - 1} title="Refazer">
            <Redo2 size={12} />
          </button>
          <button className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all ${dragMode ? 'bg-accent text-white' : 'text-text-secondary hover:text-text hover:bg-bg-hover'}`}
            onClick={() => setDragMode(v => !v)} title="Modo arrastar legenda">
            {dragMode ? <Move size={13} /> : <MousePointer2 size={13} />}
            {dragMode ? 'Arrastar' : 'Selecionar'}
          </button>
          <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium text-text-secondary hover:text-text hover:bg-bg-hover transition-all" onClick={onClose}>
            <ArrowLeft size={13} /> Voltar
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left: preview + timeline */}
        <div className="flex flex-col flex-1 min-w-0 min-h-0">
          {/* Preview area */}
          <div className="relative flex flex-1 min-h-0 items-center justify-center bg-bg-secondary overflow-hidden">
            {/* Toolbar overlay */}
            <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-3 py-1.5 z-20 bg-gradient-to-b from-black/50 to-transparent pointer-events-none">
              <div className="flex items-center gap-1 pointer-events-auto">
                <button className="flex items-center justify-center w-6 h-6 rounded text-text-secondary hover:text-text hover:bg-white/10 transition-all" onClick={() => setZoom(z => Math.max(50, z - 25))}><ZoomOut size={12} /></button>
                <span className="text-[10px] text-text-secondary w-8 text-center">{zoom}%</span>
                <button className="flex items-center justify-center w-6 h-6 rounded text-text-secondary hover:text-text hover:bg-white/10 transition-all" onClick={() => setZoom(z => Math.min(200, z + 25))}><ZoomIn size={12} /></button>
                <button className="flex items-center justify-center w-6 h-6 rounded text-text-secondary hover:text-text hover:bg-white/10 transition-all" onClick={() => setZoom(100)}><Maximize size={12} /></button>
              </div>
              <span className="text-[9px] font-bold text-accent-light bg-accent/20 px-2 py-0.5 rounded tracking-wide pointer-events-auto">LIVE PREVIEW</span>
            </div>

            {/* Video preview - fits within container */}
            <div className="flex items-center justify-center w-full h-full" style={{ transform: `scale(${zoom / 100})` }}>
              <div className="relative h-full max-h-full overflow-hidden rounded-md" style={{ aspectRatio: '9 / 16' }}>
                <video
                  ref={previewVideoRef}
                  src={videoSrc}
                  className="absolute inset-0 w-full h-full object-cover rounded-md shadow-2xl z-10"
                  playsInline
                  crossOrigin="anonymous"
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  onEnded={() => setIsPlaying(false)}
                  onLoadedMetadata={(e) => {
                    setVideoDuration(e.target.duration)
                    setVideoSize({ w: e.target.videoWidth, h: e.target.videoHeight })
                  }}
                />
                {meta?.segmentos && (
                  <LiveSubtitle
                    videoRef={previewVideoRef}
                    segmentos={meta.segmentos}
                    inicioGlobal={meta.inicio || 0}
                    style={editConfig.subtitle_style}
                    fontFamily={editConfig.font_family}
                    fontSize={editConfig.font_size}
                    marginBottom={editConfig.text_margin_bottom}
                    highlightColor={editConfig.highlight_color}
                    baseColor={editConfig.base_color}
                    onDrag={(y) => handleChange('text_margin_bottom', y)}
                    onResize={(s) => handleChange('font_size', s)}
                    dragMode={dragMode}
                  />
                )}
              </div>
            </div>

            {/* Playback controls - bottom of preview */}
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-2 z-20">
              <button className="flex items-center justify-center w-8 h-8 rounded-md bg-black/50 backdrop-blur text-white hover:bg-black/70 transition-all" onClick={() => stepFrame(-1)}><SkipBack size={14} /></button>
              <button className="flex items-center justify-center w-10 h-10 rounded-full bg-accent text-white hover:bg-accent-hover transition-all shadow-lg" onClick={togglePlayPause}>
                {isPlaying ? <Pause size={16} /> : <Play size={16} />}
              </button>
              <button className="flex items-center justify-center w-8 h-8 rounded-md bg-black/50 backdrop-blur text-white hover:bg-black/70 transition-all" onClick={() => stepFrame(1)}><SkipForward size={14} /></button>
              <button className="px-2 py-1 ml-1 text-[11px] font-medium text-white bg-black/50 backdrop-blur border border-white/10 rounded-md hover:bg-black/70 transition-all" onClick={cycleSpeed}>{playbackSpeed}x</button>
            </div>
          </div>

          <Timeline
            videoRef={previewVideoRef}
            duration={videoDuration}
            segmentos={meta?.segmentos || []}
            inicioGlobal={meta?.inicio || 0}
          />
        </div>

        {/* Right: controls sidebar */}
        <div className="w-[180px] shrink-0 border-l border-border flex flex-col overflow-hidden bg-bg-secondary">
          <div className="flex-1 min-h-0 overflow-y-auto p-2 flex flex-col gap-2">
            <div>
              <label className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary mb-1.5">
                <Type size={11} className="text-text-muted" /> Estilo da Legenda
              </label>
              <div className="grid grid-cols-4 gap-1">
                {SUBTITLE_STYLES.map(s => (
                  <button
                    key={s.value}
                    className={`px-1 py-1.5 rounded text-[9px] font-medium transition-all border ${editConfig.subtitle_style === s.value ? 'border-accent bg-accent/10 text-accent-light' : 'border-border text-text-secondary hover:border-border-light hover:text-text'}`}
                    onClick={() => handleChange('subtitle_style', s.value)}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary mb-1.5">
                <Type size={11} className="text-text-muted" /> Fonte
              </label>
              <select
                className="w-full px-2 py-1.5 bg-bg-elevated border border-border rounded text-[11px] text-text outline-none focus:border-accent cursor-pointer"
                value={editConfig.font_family}
                onChange={(e) => handleChange('font_family', e.target.value)}
              >
                {FONT_OPTIONS.map(f => (
                  <option key={f.value} value={f.value} style={{ fontFamily: f.css, fontWeight: f.weight }}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary mb-1.5">
                <Type size={11} className="text-text-muted" /> Tamanho da Fonte
              </label>
              <div className="flex items-center gap-2">
                <input type="range" className="flex-1 cursor-pointer accent-accent" min={16} max={120} value={editConfig.font_size}
                  onChange={(e) => handleChange('font_size', parseInt(e.target.value))} />
                <input type="number" className="w-12 px-1 py-0.5 bg-bg-elevated border border-border rounded text-[11px] text-text text-center outline-none focus:border-accent min-w-0"
                  min={16} max={120} value={editConfig.font_size}
                  onChange={(e) => handleChange('font_size', Math.max(16, Math.min(120, parseInt(e.target.value) || 16)))} />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-medium text-text-secondary mb-1.5">Posicao Vertical</label>
              <div className="flex items-center gap-2">
                <input type="range" className="flex-1 cursor-pointer accent-accent" min={20} max={800} value={editConfig.text_margin_bottom}
                  onChange={(e) => handleChange('text_margin_bottom', parseInt(e.target.value))} />
                <input type="number" className="w-12 px-1 py-0.5 bg-bg-elevated border border-border rounded text-[11px] text-text text-center outline-none focus:border-accent min-w-0"
                  min={20} max={800} value={editConfig.text_margin_bottom}
                  onChange={(e) => handleChange('text_margin_bottom', Math.max(20, Math.min(800, parseInt(e.target.value) || 20)))} />
              </div>
              {!dragMode && (
                <div className="text-[10px] text-text-muted mt-1">Ative o modo arrastar para mover a legenda direto no video</div>
              )}
            </div>

            <div>
              <label className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary mb-1.5">
                <Palette size={11} className="text-text-muted" /> Cores
              </label>
              <div className="flex gap-3">
                <div className="flex flex-col items-center gap-1">
                  <div className="w-8 h-8 rounded-md border border-border-light overflow-hidden cursor-pointer">
                    <input type="color" value={editConfig.highlight_color} className="w-10 h-10 -m-1 cursor-pointer"
                      onChange={(e) => handleChange('highlight_color', e.target.value)} />
                  </div>
                  <span className="text-[9px] text-text-muted">Destaque</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <div className="w-8 h-8 rounded-md border border-border-light overflow-hidden cursor-pointer">
                    <input type="color" value={editConfig.base_color} className="w-10 h-10 -m-1 cursor-pointer"
                      onChange={(e) => handleChange('base_color', e.target.value)} />
                  </div>
                  <span className="text-[9px] text-text-muted">Base</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary">
                <Crop size={11} className="text-text-muted" /> Crop 9:16
              </label>
              <div className={`w-8 h-4 rounded-full cursor-pointer transition-all ${editConfig.crop_vertical ? 'bg-accent' : 'bg-bg-elevated border border-border'}`}
                onClick={() => handleChange('crop_vertical', !editConfig.crop_vertical)}>
                <div className={`w-3 h-3 bg-white rounded-full m-0.5 transition-transform ${editConfig.crop_vertical ? 'translate-x-4' : ''}`} />
              </div>
            </div>
          </div>

          <div className="p-2 border-t border-border shrink-0">
            <button className="flex items-center justify-center gap-1.5 w-full px-3 py-1.5 bg-accent text-white rounded-md text-[11px] font-medium hover:bg-accent-hover transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              onClick={() => onRerender(editConfig)} disabled={processing}>
              {processing ? (
                <><Loader2 size={14} className="animate-spin" /> Renderizando...</>
              ) : (
                <><RotateCcw size={14} /> Re-renderizar</>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
