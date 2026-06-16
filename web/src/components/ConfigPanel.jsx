import { useState } from 'react'
import {
  Type, Sparkles, SlidersHorizontal, ChevronDown, RotateCcw,
  Palette, MoveVertical, Hash, Brain, ScanSearch,
  Crop, ZoomIn, Timer, Volume2, Save, Plus,
} from 'lucide-react'

function SectionHeader({ icon: Icon, title, collapsed, onToggle, onReset }) {
  return (
    <div
      className={`section-header ${collapsed ? 'collapsed' : ''}`}
      onClick={onToggle}
    >
      <Icon className="section-icon" />
      <span>{title}</span>
      {onReset && (
        <RotateCcw
          className="section-reset"
          size={12}
          onClick={(e) => { e.stopPropagation(); onReset() }}
          title="Resetar para padrao"
        />
      )}
      <ChevronDown className="section-chevron" />
    </div>
  )
}

const STYLE_OPTIONS = [
  { value: 'karaoke', label: 'Karaoke', preview: { background: 'linear-gradient(90deg, #1a1a2e, #1a1a2e 40%, #f59e0b 40%)', color: '#fff' } },
  { value: 'neon', label: 'Neon', preview: { background: '#0a0a0a', color: '#00ffff', textShadow: '0 0 8px #00ffff' } },
  { value: 'box', label: 'Box', preview: { background: '#222', color: '#fff', border: '1px solid #555' } },
  { value: 'sombra', label: 'Sombra', preview: { background: 'transparent', color: '#fff', textShadow: '2px 2px 4px #000' } },
]

export default function ConfigPanel({ config, defaults, onUpdate, disabled }) {
  const [sections, setSections] = useState({ subtitle: true, processing: true, effects: true })
  const [presets, setPresets] = useState(() => {
    try { return JSON.parse(localStorage.getItem('dcb-presets') || '[]') } catch { return [] }
  })
  const [presetName, setPresetName] = useState('')
  const [showSaveInput, setShowSaveInput] = useState(false)

  function toggleSection(key) {
    setSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  function handleChange(key, value) {
    onUpdate({ [key]: value })
  }

  function handleReset(section) {
    if (!defaults) return
    const keys = {
      subtitle: ['font_size', 'subtitle_style', 'highlight_color', 'base_color', 'text_margin_bottom'],
      processing: ['max_cuts', 'whisper_model', 'detect_method'],
      effects: ['crop_vertical', 'zoom_dinamico', 'fade_transition', 'bg_music_volume'],
    }
    const resetObj = {}
    keys[section]?.forEach(k => { if (defaults[k] !== undefined) resetObj[k] = defaults[k] })
    onUpdate(resetObj)
  }

  function savePreset() {
    if (!presetName.trim() || !config) return
    const newPresets = [...presets, { name: presetName.trim(), config: { ...config } }]
    setPresets(newPresets)
    localStorage.setItem('dcb-presets', JSON.stringify(newPresets))
    setPresetName('')
    setShowSaveInput(false)
  }

  function loadPreset(idx) {
    if (presets[idx]?.config) onUpdate(presets[idx].config)
  }

  function deletePreset(idx) {
    const newPresets = presets.filter((_, i) => i !== idx)
    setPresets(newPresets)
    localStorage.setItem('dcb-presets', JSON.stringify(newPresets))
  }

  if (!config || !defaults) {
    return (
      <div style={{ padding: 12 }}>
        <div className="skeleton skeleton-title" />
        <div className="skeleton skeleton-text" />
        <div className="skeleton skeleton-text short" />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <div className="presets-row">
        <select
          className="presets-select"
          onChange={(e) => { if (e.target.value === '__save__') setShowSaveInput(true); else if (e.target.value.startsWith('__del__')) deletePreset(parseInt(e.target.value.split(':')[1])); else if (e.target.value) loadPreset(parseInt(e.target.value)); e.target.value = '' }}
          value=""
        >
          <option value="">Presets...</option>
          {presets.map((p, i) => (
            <option key={i} value={i}>{p.name}</option>
          ))}
          {presets.length > 0 && <option disabled>──────────</option>}
          {presets.map((_, i) => (
            <option key={`del-${i}`} value={`__del__:${i}`}>Remover "{presets[i].name}"</option>
          ))}
          <option value="__save__">+ Salvar atual...</option>
        </select>
      </div>

      {showSaveInput && (
        <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
          <input
            className="form-input"
            style={{ fontSize: 11, padding: '4px 8px' }}
            placeholder="Nome do preset"
            value={presetName}
            onChange={(e) => setPresetName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && savePreset()}
          />
          <button className="presets-btn" onClick={savePreset} title="Salvar"><Save size={12} /></button>
          <button className="presets-btn" onClick={() => setShowSaveInput(false)} title="Cancelar">x</button>
        </div>
      )}

      <div className="sidebar-section">
        <SectionHeader icon={Type} title="Legenda" collapsed={!sections.subtitle} onToggle={() => toggleSection('subtitle')} onReset={() => handleReset('subtitle')} />
        <div className={`section-content ${!sections.subtitle ? 'collapsed' : ''}`} style={{ maxHeight: sections.subtitle ? '800px' : '0' }}>
          <div className="form-group">
            <label className="form-label">
              <SlidersHorizontal className="form-label-icon" />
              Tamanho da Fonte
            </label>
            <div className="range-row">
              <input type="range" className="range-input" min="20" max="100" value={config.font_size}
                onChange={(e) => handleChange('font_size', parseInt(e.target.value))} disabled={disabled} />
              <input className="range-value-input" type="number" min="20" max="100" value={config.font_size}
                onChange={(e) => handleChange('font_size', Math.max(20, Math.min(100, parseInt(e.target.value) || 20)))} disabled={disabled} />
              <span className="range-value">px</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label"><Type className="form-label-icon" /> Estilo</label>
            <div className="style-options">
              {STYLE_OPTIONS.map(s => (
                <div
                  key={s.value}
                  className={`style-option ${config.subtitle_style === s.value ? 'active' : ''}`}
                  onClick={() => !disabled && handleChange('subtitle_style', s.value)}
                >
                  <div className="style-option-preview" style={s.preview}>Aa</div>
                  <span>{s.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label"><Palette className="form-label-icon" /> Cores</label>
            <div className="color-row">
              <div className="color-item">
                <div className="color-input-wrapper">
                  <input type="color" value={config.highlight_color}
                    onChange={(e) => handleChange('highlight_color', e.target.value)} disabled={disabled} />
                </div>
                <span className="color-label">Destaque</span>
              </div>
              <div className="color-item">
                <div className="color-input-wrapper">
                  <input type="color" value={config.base_color}
                    onChange={(e) => handleChange('base_color', e.target.value)} disabled={disabled} />
                </div>
                <span className="color-label">Base</span>
              </div>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label"><MoveVertical className="form-label-icon" /> Margem Inferior</label>
            <div className="range-row">
              <input type="range" className="range-input" min="40" max="400" value={config.text_margin_bottom}
                onChange={(e) => handleChange('text_margin_bottom', parseInt(e.target.value))} disabled={disabled} />
              <input className="range-value-input" type="number" min="40" max="400" value={config.text_margin_bottom}
                onChange={(e) => handleChange('text_margin_bottom', Math.max(40, Math.min(400, parseInt(e.target.value) || 40)))} disabled={disabled} />
              <span className="range-value">px</span>
            </div>
          </div>
        </div>
      </div>

      <div className="sidebar-section">
        <SectionHeader icon={Sparkles} title="Processamento" collapsed={!sections.processing} onToggle={() => toggleSection('processing')} onReset={() => handleReset('processing')} />
        <div className={`section-content ${!sections.processing ? 'collapsed' : ''}`} style={{ maxHeight: sections.processing ? '600px' : '0' }}>
          <div className="form-group">
            <label className="form-label"><Hash className="form-label-icon" /> Max Cortes</label>
            <div className="range-row">
              <input type="range" className="range-input" min="1" max="20" value={config.max_cuts}
                onChange={(e) => handleChange('max_cuts', parseInt(e.target.value))} disabled={disabled} />
              <input className="range-value-input" type="number" min="1" max="20" value={config.max_cuts}
                onChange={(e) => handleChange('max_cuts', Math.max(1, Math.min(20, parseInt(e.target.value) || 1)))} disabled={disabled} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label"><Brain className="form-label-icon" /> Modelo Transcrição</label>
            <select className="form-select" value={config.whisper_model}
              onChange={(e) => handleChange('whisper_model', e.target.value)} disabled={disabled}>
              <option value="parakeet">Parakeet TDT (recomendado)</option>
              <option value="small">Whisper Small</option>
              <option value="medium">Whisper Medium (lento)</option>
              <option value="large">Whisper Large (mais lento)</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label"><ScanSearch className="form-label-icon" /> Deteccao</label>
            <select className="form-select" value={config.detect_method}
              onChange={(e) => handleChange('detect_method', e.target.value)} disabled={disabled}>
              <option value="ia">IA (Ollama/OpenAI)</option>
              <option value="heuristicas">Heuristicas</option>
              <option value="ambos">Ambos</option>
            </select>
          </div>
        </div>
      </div>

      <div className="sidebar-section">
        <SectionHeader icon={SlidersHorizontal} title="Efeitos" collapsed={!sections.effects} onToggle={() => toggleSection('effects')} onReset={() => handleReset('effects')} />
        <div className={`section-content ${!sections.effects ? 'collapsed' : ''}`} style={{ maxHeight: sections.effects ? '600px' : '0' }}>
          <div className="form-group">
            <div className="toggle-row">
              <label className="form-label" style={{ marginBottom: 0 }}><Crop className="form-label-icon" /> Crop Vertical (9:16)</label>
              <div className={`toggle ${config.crop_vertical ? 'active' : ''}`}
                onClick={() => !disabled && handleChange('crop_vertical', !config.crop_vertical)} />
            </div>
          </div>
          <div className="form-group">
            <div className="toggle-row">
              <label className="form-label" style={{ marginBottom: 0 }}><ZoomIn className="form-label-icon" /> Zoom Dinamico</label>
              <div className={`toggle ${config.zoom_dinamico ? 'active' : ''}`}
                onClick={() => !disabled && handleChange('zoom_dinamico', !config.zoom_dinamico)} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label"><Timer className="form-label-icon" /> Fade In/Out</label>
            <div className="range-row">
              <input type="range" className="range-input" min="0" max="15"
                value={Math.round((config.fade_transition || 0) * 10)}
                onChange={(e) => handleChange('fade_transition', parseInt(e.target.value) / 10)} disabled={disabled} />
              <span className="range-value">{(config.fade_transition || 0).toFixed(1)}s</span>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label"><Volume2 className="form-label-icon" /> Volume Musica</label>
            <div className="range-row">
              <input type="range" className="range-input" min="0" max="50"
                value={Math.round(config.bg_music_volume * 100)}
                onChange={(e) => handleChange('bg_music_volume', parseInt(e.target.value) / 100)} disabled={disabled} />
              <span className="range-value">{Math.round(config.bg_music_volume * 100)}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
