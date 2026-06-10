import { useState, useEffect, useRef, useCallback } from 'react'
import {
  ArrowLeft, Type, MoveVertical, Crop, RotateCcw, Loader2,
  Monitor, Image, SlidersHorizontal, Palette, ZoomIn, ZoomOut,
  Maximize, Columns, Undo2, Redo2, Play, Pause,
  SkipBack, SkipForward,
} from 'lucide-react'

export default function VideoEditor({ cut, config, onRerender, onClose, processing }) {
  const [editConfig, setEditConfig] = useState({
    font_size: config?.font_size || 52,
    text_margin_bottom: config?.text_margin_bottom || 180,
    subtitle_style: config?.subtitle_style || 'karaoke',
    highlight_color: config?.highlight_color || '#FFFF32',
    base_color: config?.base_color || '#B4B4B4',
    crop_vertical: config?.crop_vertical ?? true,
  })
  const [previewUrl, setPreviewUrl] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [zoom, setZoom] = useState(100)
  const [showCompare, setShowCompare] = useState(false)
  const [history, setHistory] = useState([])
  const [historyIdx, setHistoryIdx] = useState(-1)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [isPlaying, setIsPlaying] = useState(false)
  const debounceRef = useRef(null)
  const videoRef = useRef(null)
  const prevUrlRef = useRef(null)
  const abortRef = useRef(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    const initial = {
      font_size: config?.font_size || 52,
      text_margin_bottom: config?.text_margin_bottom || 180,
      subtitle_style: config?.subtitle_style || 'karaoke',
      highlight_color: config?.highlight_color || '#FFFF32',
      base_color: config?.base_color || '#B4B4B4',
      crop_vertical: config?.crop_vertical ?? true,
    }
    setEditConfig(initial)
    setHistory([initial])
    setHistoryIdx(0)
  }, [cut?.cut_id])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(fetchPreview, 400)
    return () => {
      clearTimeout(debounceRef.current)
      if (abortRef.current) abortRef.current.abort()
    }
  }, [editConfig, cut?.cut_id])

  useEffect(() => {
    return () => {
      if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current)
    }
  }, [])

  async function fetchPreview() {
    if (!cut?.cut_id || !mountedRef.current) return
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setPreviewLoading(true)
    try {
      const res = await fetch(`/api/cut/${encodeURIComponent(cut.cut_id)}/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editConfig),
        signal: controller.signal,
      })
      if (!mountedRef.current) return
      if (res.ok) {
        const blob = await res.blob()
        if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current)
        const url = URL.createObjectURL(blob)
        prevUrlRef.current = url
        setPreviewUrl(url)
      }
    } catch {
      if (controller.signal.aborted) return
    }
    if (mountedRef.current) setPreviewLoading(false)
  }

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

  function handleRerender() {
    onRerender(editConfig)
  }

  function togglePlayPause() {
    const v = videoRef.current
    if (!v) return
    if (v.paused) { v.play(); setIsPlaying(true) }
    else { v.pause(); setIsPlaying(false) }
  }

  function stepFrame(direction) {
    const v = videoRef.current
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
    if (videoRef.current) videoRef.current.playbackRate = next
  }

  return (
    <div className="panel slide-in-right">
      <div className="panel-header">
        <div className="panel-header-left">
          <Image className="panel-icon" />
          <span className="panel-title">Editor - {cut.titulo}</span>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          <ArrowLeft size={13} /> Voltar
        </button>
      </div>

      <div className="panel-body">
        <div className="editor-undo-row" style={{ marginBottom: 10 }}>
          <button className="editor-undo-btn" onClick={handleUndo} disabled={historyIdx <= 0}>
            <Undo2 size={12} /> Desfazer
          </button>
          <button className="editor-undo-btn" onClick={handleRedo} disabled={historyIdx >= history.length - 1}>
            <Redo2 size={12} /> Refazer
          </button>
        </div>

        <div className="editor-layout">
          <div className="editor-preview-container">
            <div className="editor-preview-toolbar">
              <div className="editor-preview-toolbar-left">
                <button className="editor-zoom-btn" onClick={() => setZoom(z => Math.max(50, z - 25))}><ZoomOut size={13} /></button>
                <span className="editor-zoom-label">{zoom}%</span>
                <button className="editor-zoom-btn" onClick={() => setZoom(z => Math.min(200, z + 25))}><ZoomIn size={13} /></button>
                <button className="editor-zoom-btn" onClick={() => setZoom(100)}><Maximize size={13} /></button>
              </div>
              <div className="editor-preview-toolbar-right">
                <button className={`editor-compare-btn ${showCompare ? 'active' : ''}`}
                  onClick={() => setShowCompare(v => !v)}>
                  <Columns size={12} /> Comparar
                </button>
              </div>
            </div>

            <div style={{ display: showCompare ? 'grid' : 'block', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div className="editor-preview-area" style={{ maxHeight: showCompare ? 360 : 480, transform: `scale(${zoom / 100})`, transformOrigin: 'top center' }}>
                {previewUrl ? (
                  <img src={previewUrl} alt="Preview" className="editor-preview-img" />
                ) : (
                  <div className="editor-preview-placeholder">Carregando preview...</div>
                )}
                {previewLoading && (
                  <div className="editor-preview-loading">
                    <Loader2 size={11} className="spin" /> atualizando
                  </div>
                )}
              </div>
              {showCompare && (
                <div className="editor-preview-area" style={{ maxHeight: 360 }}>
                  <video
                    ref={videoRef}
                    src={`/api/cuts/${encodeURIComponent(cut.arquivo)}`}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    onEnded={() => setIsPlaying(false)}
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                  />
                </div>
              )}
            </div>
          </div>

          <div className="editor-controls">
            <div className="panel">
              <div className="panel-header">
                <div className="panel-header-left">
                  <SlidersHorizontal className="panel-icon" size={14} />
                  <span className="panel-title" style={{ fontSize: 11 }}>Configuracoes</span>
                </div>
              </div>
              <div className="panel-body">
                <div className="form-group">
                  <label className="form-label"><Type className="form-label-icon" /> Fonte</label>
                  <div className="range-row">
                    <input type="range" className="range-input" min="16" max="120" value={editConfig.font_size}
                      onChange={(e) => handleChange('font_size', parseInt(e.target.value))} />
                    <input className="range-value-input" type="number" min="16" max="120" value={editConfig.font_size}
                      onChange={(e) => handleChange('font_size', Math.max(16, Math.min(120, parseInt(e.target.value) || 16)))} />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label"><MoveVertical className="form-label-icon" /> Posicao</label>
                  <div className="range-row">
                    <input type="range" className="range-input" min="40" max="800" value={editConfig.text_margin_bottom}
                      onChange={(e) => handleChange('text_margin_bottom', parseInt(e.target.value))} />
                    <input className="range-value-input" type="number" min="40" max="800" value={editConfig.text_margin_bottom}
                      onChange={(e) => handleChange('text_margin_bottom', Math.max(40, Math.min(800, parseInt(e.target.value) || 40)))} />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label"><Type className="form-label-icon" /> Estilo</label>
                  <select className="form-select" value={editConfig.subtitle_style}
                    onChange={(e) => handleChange('subtitle_style', e.target.value)}>
                    <option value="karaoke">Karaoke</option>
                    <option value="neon">Neon</option>
                    <option value="box">Box</option>
                    <option value="sombra">Sombra</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label"><Palette className="form-label-icon" /> Cores</label>
                  <div className="color-row">
                    <div className="color-item">
                      <div className="color-input-wrapper">
                        <input type="color" value={editConfig.highlight_color}
                          onChange={(e) => handleChange('highlight_color', e.target.value)} />
                      </div>
                      <span className="color-label">Destaque</span>
                    </div>
                    <div className="color-item">
                      <div className="color-input-wrapper">
                        <input type="color" value={editConfig.base_color}
                          onChange={(e) => handleChange('base_color', e.target.value)} />
                      </div>
                      <span className="color-label">Base</span>
                    </div>
                  </div>
                </div>
                <div className="form-group">
                  <div className="toggle-row">
                    <label className="form-label" style={{ marginBottom: 0 }}><Crop className="form-label-icon" /> Crop 9:16</label>
                    <div className={`toggle ${editConfig.crop_vertical ? 'active' : ''}`}
                      onClick={() => handleChange('crop_vertical', !editConfig.crop_vertical)} />
                  </div>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <div className="panel-header-left">
                  <Monitor className="panel-icon" size={14} />
                  <span className="panel-title" style={{ fontSize: 11 }}>Video Original</span>
                </div>
              </div>
              <div className="panel-body" style={{ padding: 8 }}>
                <div className="editor-video-player">
                  <video ref={videoRef} src={`/api/cuts/${encodeURIComponent(cut.arquivo)}`}
                    onPlay={() => setIsPlaying(true)} onPause={() => setIsPlaying(false)}
                    onEnded={() => setIsPlaying(false)} />
                </div>
                <div className="editor-playback" style={{ marginTop: 6 }}>
                  <button className="editor-playback-btn" onClick={() => stepFrame(-1)}><SkipBack size={12} /></button>
                  <button className="editor-playback-btn play-main" onClick={togglePlayPause}>
                    {isPlaying ? <Pause size={14} /> : <Play size={14} />}
                  </button>
                  <button className="editor-playback-btn" onClick={() => stepFrame(1)}><SkipForward size={12} /></button>
                  <button className="editor-playback-speed" onClick={cycleSpeed}>{playbackSpeed}x</button>
                </div>
              </div>
            </div>

            <button className="btn btn-primary" onClick={handleRerender} disabled={processing} style={{ width: '100%' }}>
              {processing ? (
                <><Loader2 size={14} className="spin" /> Renderizando...</>
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
