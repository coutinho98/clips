import { useState, useEffect, useRef, useCallback } from 'react'

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
  const debounceRef = useRef(null)

  useEffect(() => {
    fetchPreview()
    return () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }
  }, [])

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
    <div className="card" style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Editor - {cut.titulo}</h2>
        <button className="btn btn-sm" onClick={onClose} style={{ background: 'var(--surface-2)', color: 'var(--text)' }}>
          Fechar
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label>Preview da Legenda</label>
          </div>
          <div style={{
            position: 'relative',
            background: '#000',
            borderRadius: 8,
            overflow: 'hidden',
            aspectRatio: '9/16',
            maxHeight: '500px',
          }}>
            {previewUrl ? (
              <img
                src={previewUrl}
                alt="Preview"
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            ) : (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                height: '100%', color: 'var(--text-dim)', fontSize: 13
              }}>
                Carregando preview...
              </div>
            )}
            {previewLoading && (
              <div style={{
                position: 'absolute', top: 8, right: 8,
                background: 'var(--accent)', color: '#fff',
                padding: '2px 8px', borderRadius: 4, fontSize: 11,
              }}>
                atualizando...
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="form-group" style={{ marginBottom: 8 }}>
            <label>Configuracoes da Legenda</label>
          </div>

          <div className="form-group">
            <label>Tamanho da Fonte</label>
            <div className="range-row">
              <input
                type="range" min="16" max="120"
                value={editConfig.font_size}
                onChange={(e) => handleChange('font_size', parseInt(e.target.value))}
              />
              <span className="range-value">{editConfig.font_size}px</span>
            </div>
          </div>

          <div className="form-group">
            <label>Posicao Vertical</label>
            <div className="range-row">
              <input
                type="range" min="40" max="800"
                value={editConfig.text_margin_bottom}
                onChange={(e) => handleChange('text_margin_bottom', parseInt(e.target.value))}
              />
              <span className="range-value">{editConfig.text_margin_bottom}px</span>
            </div>
          </div>

          <div className="form-group">
            <label>Estilo</label>
            <select
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
            <div className="toggle-row">
              <label>Crop 9:16</label>
              <div
                className={`toggle ${editConfig.crop_vertical ? 'active' : ''}`}
                onClick={() => handleChange('crop_vertical', !editConfig.crop_vertical)}
              />
            </div>
          </div>

          <hr className="divider" />

          <div className="form-group">
            <label>Video Original</label>
            <div className="video-player" style={{ borderRadius: 8, overflow: 'hidden' }}>
              <video
                src={`/api/cuts/${encodeURIComponent(cut.arquivo)}`}
                controls
                style={{ width: '100%', maxHeight: '200px', display: 'block' }}
              />
            </div>
          </div>

          <button
            className="btn btn-primary"
            onClick={handleRerender}
            disabled={processing}
            style={{ marginTop: 8 }}
          >
            {processing ? 'Renderizando...' : 'Re-renderizar'}
          </button>
        </div>
      </div>
    </div>
  )
}
