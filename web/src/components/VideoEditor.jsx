import { useState, useEffect, useRef } from 'react'
import {
  ArrowLeft,
  Type,
  MoveVertical,
  Crop,
  RotateCcw,
  Loader2,
  Monitor,
  Image,
  SlidersHorizontal,
  Palette,
} from 'lucide-react'

export default function VideoEditor({ cut, config, onRerender, onClose, processing }) {
  const defaultConfig = {
    font_size: config?.font_size || 52,
    text_margin_bottom: config?.text_margin_bottom || 180,
    subtitle_style: config?.subtitle_style || 'karaoke',
    highlight_color: config?.highlight_color || '#FFFF32',
    base_color: config?.base_color || '#B4B4B4',
    crop_vertical: config?.crop_vertical ?? true,
  }
  const [editConfig, setEditConfig] = useState(defaultConfig)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const debounceRef = useRef(null)

  useEffect(() => {
    setEditConfig({
      font_size: config?.font_size || 52,
      text_margin_bottom: config?.text_margin_bottom || 180,
      subtitle_style: config?.subtitle_style || 'karaoke',
      highlight_color: config?.highlight_color || '#FFFF32',
      base_color: config?.base_color || '#B4B4B4',
      crop_vertical: config?.crop_vertical ?? true,
    })
  }, [cut?.cut_id])

  useEffect(() => {
    fetchPreview()
    return () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }
  }, [cut?.cut_id])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(fetchPreview, 400)
    return () => clearTimeout(debounceRef.current)
  }, [editConfig])

  async function fetchPreview() {
    if (!cut?.cut_id) return
    setPreviewLoading(true)
    try {
      const res = await fetch(`/api/cut/${encodeURIComponent(cut.cut_id)}/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editConfig),
      })
      if (res.ok) {
        const blob = await res.blob()
        if (previewUrl) URL.revokeObjectURL(previewUrl)
        setPreviewUrl(URL.createObjectURL(blob))
      }
    } catch {}
    setPreviewLoading(false)
  }

  function handleChange(key, value) {
    setEditConfig(prev => ({ ...prev, [key]: value }))
  }

  function handleRerender() {
    onRerender(editConfig)
  }

  return (
    <div className="panel fade-in">
      <div className="panel-header">
        <div className="panel-header-left">
          <Image className="panel-icon" />
          <span className="panel-title">Editor - {cut.titulo}</span>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          <ArrowLeft size={14} />
          Voltar
        </button>
      </div>

      <div className="panel-body">
        <div className="editor-layout">
          <div className="editor-preview-area">
            {previewUrl ? (
              <img
                src={previewUrl}
                alt="Preview"
                className="editor-preview-img"
              />
            ) : (
              <div className="editor-preview-placeholder">
                Carregando preview...
              </div>
            )}
            {previewLoading && (
              <div className="editor-preview-loading">
                <Loader2 size={12} className="spin" />
                atualizando
              </div>
            )}
          </div>

          <div className="editor-controls">
            <div className="panel">
              <div className="panel-header">
                <div className="panel-header-left">
                  <SlidersHorizontal className="panel-icon" size={15} />
                  <span className="panel-title" style={{ fontSize: 12 }}>Configuracoes</span>
                </div>
              </div>
              <div className="panel-body">
                <div className="form-group">
                  <label className="form-label">
                    <Type className="form-label-icon" />
                    Tamanho da Fonte
                  </label>
                  <div className="range-row">
                    <input
                      type="range"
                      className="range-input"
                      min="16"
                      max="120"
                      value={editConfig.font_size}
                      onChange={(e) => handleChange('font_size', parseInt(e.target.value))}
                    />
                    <span className="range-value">{editConfig.font_size}px</span>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    <MoveVertical className="form-label-icon" />
                    Posicao Vertical
                  </label>
                  <div className="range-row">
                    <input
                      type="range"
                      className="range-input"
                      min="40"
                      max="800"
                      value={editConfig.text_margin_bottom}
                      onChange={(e) => handleChange('text_margin_bottom', parseInt(e.target.value))}
                    />
                    <span className="range-value">{editConfig.text_margin_bottom}px</span>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    <Type className="form-label-icon" />
                    Estilo
                  </label>
                  <select
                    className="form-select"
                    value={editConfig.subtitle_style}
                    onChange={(e) => handleChange('subtitle_style', e.target.value)}
                  >
                    <option value="karaoke">Karaoke</option>
                    <option value="neon">Neon</option>
                    <option value="box">Box</option>
                    <option value="sombra">Sombra</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    <Palette className="form-label-icon" />
                    Cores
                  </label>
                  <div className="color-row">
                    <div className="color-item">
                      <div className="color-input-wrapper">
                        <input
                          type="color"
                          value={editConfig.highlight_color}
                          onChange={(e) => handleChange('highlight_color', e.target.value)}
                        />
                      </div>
                      <span className="color-label">Destaque</span>
                    </div>
                    <div className="color-item">
                      <div className="color-input-wrapper">
                        <input
                          type="color"
                          value={editConfig.base_color}
                          onChange={(e) => handleChange('base_color', e.target.value)}
                        />
                      </div>
                      <span className="color-label">Base</span>
                    </div>
                  </div>
                </div>

                <div className="form-group">
                  <div className="toggle-row">
                    <label className="form-label" style={{ marginBottom: 0 }}>
                      <Crop className="form-label-icon" />
                      Crop 9:16
                    </label>
                    <div
                      className={`toggle ${editConfig.crop_vertical ? 'active' : ''}`}
                      onClick={() => handleChange('crop_vertical', !editConfig.crop_vertical)}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <div className="panel-header-left">
                  <Monitor className="panel-icon" size={15} />
                  <span className="panel-title" style={{ fontSize: 12 }}>Video Original</span>
                </div>
              </div>
              <div className="panel-body" style={{ padding: '10px' }}>
                <div className="editor-video-player">
                  <video
                    src={`/api/cuts/${encodeURIComponent(cut.arquivo)}`}
                    controls
                  />
                </div>
              </div>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleRerender}
              disabled={processing}
              style={{ width: '100%' }}
            >
              {processing ? (
                <>
                  <Loader2 size={15} className="spin" />
                  Renderizando...
                </>
              ) : (
                <>
                  <RotateCcw size={15} />
                  Re-renderizar
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
