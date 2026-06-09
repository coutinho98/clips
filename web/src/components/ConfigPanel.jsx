import { useState } from 'react'
import {
  Type,
  Sparkles,
  SlidersHorizontal,
  ChevronDown,
  Palette,
  MoveVertical,
  Hash,
  Brain,
  ScanSearch,
  Crop,
  ZoomIn,
  Timer,
  Volume2,
} from 'lucide-react'

function SectionHeader({ icon: Icon, title, collapsed, onToggle }) {
  return (
    <div
      className={`section-header ${collapsed ? 'collapsed' : ''}`}
      onClick={onToggle}
    >
      <Icon className="section-icon" />
      <span>{title}</span>
      <ChevronDown className="section-chevron" />
    </div>
  )
}

export default function ConfigPanel({ config, defaults, onUpdate, disabled }) {
  const [sections, setSections] = useState({
    subtitle: true,
    processing: true,
    effects: true,
  })

  function toggleSection(key) {
    setSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  function handleChange(key, value) {
    onUpdate({ [key]: value })
  }

  if (!config || !defaults) {
    return (
      <div className="panel">
        <div className="panel-body">
          <div className="empty-state" style={{ padding: 24 }}>
            <div className="empty-state-text">Carregando configuracoes...</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div className="sidebar-section">
        <SectionHeader
          icon={Type}
          title="Legenda"
          collapsed={!sections.subtitle}
          onToggle={() => toggleSection('subtitle')}
        />
        <div
          className={`section-content ${!sections.subtitle ? 'collapsed' : ''}`}
          style={{ maxHeight: sections.subtitle ? '600px' : '0' }}
        >
          <div className="form-group">
            <label className="form-label">
              <SlidersHorizontal className="form-label-icon" />
              Tamanho da Fonte
            </label>
            <div className="range-row">
              <input
                type="range"
                className="range-input"
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
            <label className="form-label">
              <Type className="form-label-icon" />
              Estilo de Legenda
            </label>
            <select
              className="form-select"
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
            <label className="form-label">
              <Palette className="form-label-icon" />
              Cores
            </label>
            <div className="color-row">
              <div className="color-item">
                <div className="color-input-wrapper">
                  <input
                    type="color"
                    value={config.highlight_color}
                    onChange={(e) => handleChange('highlight_color', e.target.value)}
                    disabled={disabled}
                  />
                </div>
                <span className="color-label">Destaque</span>
              </div>
              <div className="color-item">
                <div className="color-input-wrapper">
                  <input
                    type="color"
                    value={config.base_color}
                    onChange={(e) => handleChange('base_color', e.target.value)}
                    disabled={disabled}
                  />
                </div>
                <span className="color-label">Base</span>
              </div>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              <MoveVertical className="form-label-icon" />
              Margem Inferior
            </label>
            <div className="range-row">
              <input
                type="range"
                className="range-input"
                min="40"
                max="400"
                value={config.text_margin_bottom}
                onChange={(e) => handleChange('text_margin_bottom', parseInt(e.target.value))}
                disabled={disabled}
              />
              <span className="range-value">{config.text_margin_bottom}px</span>
            </div>
          </div>
        </div>
      </div>

      <div className="sidebar-section">
        <SectionHeader
          icon={Sparkles}
          title="Processamento"
          collapsed={!sections.processing}
          onToggle={() => toggleSection('processing')}
        />
        <div
          className={`section-content ${!sections.processing ? 'collapsed' : ''}`}
          style={{ maxHeight: sections.processing ? '500px' : '0' }}
        >
          <div className="form-group">
            <label className="form-label">
              <Hash className="form-label-icon" />
              Max Cortes
            </label>
            <div className="range-row">
              <input
                type="range"
                className="range-input"
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
            <label className="form-label">
              <Brain className="form-label-icon" />
              Modelo Whisper
            </label>
            <select
              className="form-select"
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
            <label className="form-label">
              <ScanSearch className="form-label-icon" />
              Deteccao
            </label>
            <select
              className="form-select"
              value={config.detect_method}
              onChange={(e) => handleChange('detect_method', e.target.value)}
              disabled={disabled}
            >
              <option value="ia">IA (Ollama/OpenAI)</option>
              <option value="heuristicas">Heuristicas</option>
              <option value="ambos">Ambos</option>
            </select>
          </div>
        </div>
      </div>

      <div className="sidebar-section">
        <SectionHeader
          icon={SlidersHorizontal}
          title="Efeitos"
          collapsed={!sections.effects}
          onToggle={() => toggleSection('effects')}
        />
        <div
          className={`section-content ${!sections.effects ? 'collapsed' : ''}`}
          style={{ maxHeight: sections.effects ? '500px' : '0' }}
        >
          <div className="form-group">
            <div className="toggle-row">
              <label className="form-label" style={{ marginBottom: 0 }}>
                <Crop className="form-label-icon" />
                Crop Vertical (9:16)
              </label>
              <div
                className={`toggle ${config.crop_vertical ? 'active' : ''}`}
                onClick={() => !disabled && handleChange('crop_vertical', !config.crop_vertical)}
              />
            </div>
          </div>

          <div className="form-group">
            <div className="toggle-row">
              <label className="form-label" style={{ marginBottom: 0 }}>
                <ZoomIn className="form-label-icon" />
                Zoom Dinamico (segue rosto)
              </label>
              <div
                className={`toggle ${config.zoom_dinamico ? 'active' : ''}`}
                onClick={() => !disabled && handleChange('zoom_dinamico', !config.zoom_dinamico)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              <Timer className="form-label-icon" />
              Fade In/Out
            </label>
            <div className="range-row">
              <input
                type="range"
                className="range-input"
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
            <label className="form-label">
              <Volume2 className="form-label-icon" />
              Volume Musica Fundo
            </label>
            <div className="range-row">
              <input
                type="range"
                className="range-input"
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
      </div>
    </div>
  )
}
