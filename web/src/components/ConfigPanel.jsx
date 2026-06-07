export default function ConfigPanel({ config, defaults, onUpdate, disabled }) {
  if (!config || !defaults) return <div className="card">Carregando...</div>

  function handleChange(key, value) {
    onUpdate({ [key]: value })
  }

  return (
    <div className="card">
      <h2>Configuracoes</h2>

      <div className="form-group">
        <label>Tamanho da Fonte</label>
        <div className="range-row">
          <input
            type="range"
            min="20"
            max="100"
            value={config.font_size}
            onChange={(e) => handleChange('font_size', parseInt(e.target.value))}
            disabled={disabled}
          />
          <span className="range-value">{config.font_size}px</span>
        </div>
      </div>

      <div className="form-group">
        <label>Estilo de Legenda</label>
        <select
          value={config.subtitle_style}
          onChange={(e) => handleChange('subtitle_style', e.target.value)}
          disabled={disabled}
        >
          <option value="karaoke">Karaoke (palavra a palavra)</option>
          <option value="neon">Neon</option>
          <option value="box">Box</option>
          <option value="sombra">Sombra</option>
        </select>
      </div>

      <div className="form-group">
        <label>Cor do Highlight</label>
        <div className="color-row">
          <div className="color-item">
            <input
              type="color"
              value={config.highlight_color}
              onChange={(e) => handleChange('highlight_color', e.target.value)}
              disabled={disabled}
            />
            <label>Destaque</label>
          </div>
          <div className="color-item">
            <input
              type="color"
              value={config.base_color}
              onChange={(e) => handleChange('base_color', e.target.value)}
              disabled={disabled}
            />
            <label>Base</label>
          </div>
        </div>
      </div>

      <div className="form-group">
        <label>Margem Inferior</label>
        <div className="range-row">
          <input
            type="range"
            min="40"
            max="400"
            value={config.text_margin_bottom}
            onChange={(e) => handleChange('text_margin_bottom', parseInt(e.target.value))}
            disabled={disabled}
          />
          <span className="range-value">{config.text_margin_bottom}px</span>
        </div>
      </div>

      <hr className="divider" />

      <div className="form-group">
        <label>Max Cortes</label>
        <div className="range-row">
          <input
            type="range"
            min="1"
            max="20"
            value={config.max_cuts}
            onChange={(e) => handleChange('max_cuts', parseInt(e.target.value))}
            disabled={disabled}
          />
          <span className="range-value">{config.max_cuts}</span>
        </div>
      </div>

      <div className="form-group">
        <label>Modelo Whisper</label>
        <select
          value={config.whisper_model}
          onChange={(e) => handleChange('whisper_model', e.target.value)}
          disabled={disabled}
        >
          <option value="tiny">Tiny (rapido)</option>
          <option value="base">Base</option>
          <option value="small">Small (recomendado)</option>
          <option value="medium">Medium (lento)</option>
          <option value="large">Large (mais lento)</option>
        </select>
      </div>

      <div className="form-group">
        <label>Deteccao</label>
        <select
          value={config.detect_method}
          onChange={(e) => handleChange('detect_method', e.target.value)}
          disabled={disabled}
        >
          <option value="ia">IA (Ollama/OpenAI)</option>
          <option value="heuristicas">Heuristicas</option>
          <option value="ambos">Ambos</option>
        </select>
      </div>

      <div className="form-group">
        <div className="toggle-row">
          <label>Crop Vertical (9:16)</label>
          <div
            className={`toggle ${config.crop_vertical ? 'active' : ''}`}
            onClick={() => !disabled && handleChange('crop_vertical', !config.crop_vertical)}
          />
        </div>
      </div>

      <div className="form-group">
        <div className="toggle-row">
          <label>Zoom Dinamico (segue rosto)</label>
          <div
            className={`toggle ${config.zoom_dinamico ? 'active' : ''}`}
            onClick={() => !disabled && handleChange('zoom_dinamico', !config.zoom_dinamico)}
          />
        </div>
      </div>

      <div className="form-group">
        <label>Fade In/Out</label>
        <div className="range-row">
          <input
            type="range"
            min="0"
            max="15"
            value={Math.round((config.fade_transition || 0) * 10)}
            onChange={(e) => handleChange('fade_transition', parseInt(e.target.value) / 10)}
            disabled={disabled}
          />
          <span className="range-value">{(config.fade_transition || 0).toFixed(1)}s</span>
        </div>
      </div>

      <div className="form-group">
        <label>Volume Musica Fundo</label>
        <div className="range-row">
          <input
            type="range"
            min="0"
            max="50"
            value={Math.round(config.bg_music_volume * 100)}
            onChange={(e) => handleChange('bg_music_volume', parseInt(e.target.value) / 100)}
            disabled={disabled}
          />
          <span className="range-value">{Math.round(config.bg_music_volume * 100)}%</span>
        </div>
      </div>
    </div>
  )
}
