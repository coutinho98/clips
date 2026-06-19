import { useState } from 'react'
import {
  Type, Sparkles, SlidersHorizontal, ChevronDown, RotateCcw,
  Palette, MoveVertical, Hash, Brain, ScanSearch,
  Crop, ZoomIn, Timer, Volume2, Save,
} from 'lucide-react'

const STYLE_OPTIONS = [
  { value: 'karaoke', label: 'Karaoke', preview: { background: 'linear-gradient(90deg, #1a1a2e, #1a1a2e 40%, #f59e0b 40%)', color: '#fff' } },
  { value: 'neon', label: 'Neon', preview: { background: '#0a0a0a', color: '#00ffff', textShadow: '0 0 8px #00ffff' } },
  { value: 'pop', label: 'Pop', preview: { background: '#1a1a2e', color: '#FFFF32', fontSize: '15px' } },
  { value: 'slide', label: 'Slide', preview: { background: '#16213e', color: '#FFFF32', transform: 'translateY(-2px)' } },
  { value: 'typewriter', label: 'Typewriter', preview: { background: '#0f0f0f', color: '#FFFF32', fontFamily: 'monospace' } },
  { value: 'rainbow', label: 'Rainbow', preview: { background: 'transparent', color: '#7c3aed', textShadow: '0 0 6px #7c3aed' } },
  { value: 'box', label: 'Box', preview: { background: '#222', color: '#fff', border: '1px solid #555' } },
  { value: 'sombra', label: 'Sombra', preview: { background: 'transparent', color: '#fff', textShadow: '2px 2px 4px #000' } },
]

function SectionHeader({ icon: Icon, title, collapsed, onToggle, onReset }) {
  return (
    <div
      className={`flex items-center gap-2 px-3 py-2.5 cursor-pointer hover:bg-bg-hover transition-colors select-none ${collapsed ? 'border-b border-border' : ''}`}
      onClick={onToggle}
    >
      <Icon size={13} className={collapsed ? 'text-text-secondary' : 'text-accent-light'} />
      <span className="text-[11px] font-semibold text-text flex-1">{title}</span>
      {onReset && (
        <RotateCcw
          size={11}
          className="text-text-muted hover:text-text transition-colors"
          onClick={(e) => { e.stopPropagation(); onReset() }}
          title="Resetar para padrao"
        />
      )}
      <ChevronDown size={13} className={`text-text-muted transition-transform ${collapsed ? '' : 'rotate-180'}`} />
    </div>
  )
}

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
      <div className="p-3 flex flex-col gap-2">
        <div className="h-4 bg-bg-elevated rounded animate-pulse" />
        <div className="h-3 bg-bg-elevated rounded animate-pulse" />
        <div className="h-3 bg-bg-elevated rounded w-3/4 animate-pulse" />
      </div>
    )
  }

  const Label = ({ icon: Icon, children }) => (
    <label className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary mb-1.5">
      {Icon && <Icon size={11} className="text-text-muted" />}
      {children}
    </label>
  )

  const RangeRow = ({ configKey, min, max, value, onChange, suffix }) => (
    <div className="flex items-center gap-2">
      <input type="range" className="flex-1 cursor-pointer accent-accent" min={min} max={max} value={value}
        onChange={(e) => onChange(parseInt(e.target.value))} disabled={disabled} />
      <input type="number" className="w-12 px-1 py-0.5 bg-bg-elevated border border-border rounded text-[11px] text-text text-center outline-none focus:border-accent min-w-0"
        min={min} max={max} value={value}
        onChange={(e) => onChange(Math.max(min, Math.min(max, parseInt(e.target.value) || min)))} disabled={disabled} />
      {suffix && <span className="text-[10px] text-text-muted w-4 shrink-0">{suffix}</span>}
    </div>
  )

  return (
    <div className="flex flex-col gap-0.5">
      <select
        className="w-full px-2.5 py-1.5 bg-bg-elevated border border-border rounded-md text-[11px] text-text outline-none focus:border-accent cursor-pointer transition-colors mb-1"
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

      {showSaveInput && (
        <div className="flex gap-1 mb-1.5">
          <input
            className="flex-1 min-w-0 px-2 py-1 bg-bg-elevated border border-border rounded text-[11px] text-text outline-none focus:border-accent"
            placeholder="Nome do preset"
            value={presetName}
            onChange={(e) => setPresetName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && savePreset()}
          />
          <button className="px-2 py-1 bg-bg-elevated border border-border rounded text-text-secondary hover:text-text hover:bg-bg-hover transition-all" onClick={savePreset} title="Salvar"><Save size={12} /></button>
          <button className="px-2 py-1 bg-bg-elevated border border-border rounded text-text-secondary hover:text-text hover:bg-bg-hover transition-all" onClick={() => setShowSaveInput(false)} title="Cancelar">x</button>
        </div>
      )}

      {/* Subtitle Section */}
      <div className="bg-bg-tertiary border-b border-border overflow-hidden">
        <SectionHeader icon={Type} title="Legenda" collapsed={!sections.subtitle} onToggle={() => toggleSection('subtitle')} onReset={() => handleReset('subtitle')} />
        <div className="overflow-hidden transition-all duration-200" style={{ maxHeight: sections.subtitle ? '800px' : '0' }}>
          <div className="p-3 flex flex-col gap-3">
            <div>
              <Label icon={SlidersHorizontal}>Tamanho da Fonte</Label>
              <RangeRow configKey="font_size" min={20} max={100} value={config.font_size}
                onChange={(v) => handleChange('font_size', v)} suffix="px" />
            </div>

            <div>
              <Label icon={Type}>Estilo</Label>
              <div className="grid grid-cols-4 gap-1.5">
                {STYLE_OPTIONS.map(s => (
                  <div
                    key={s.value}
                    className={`flex flex-col items-center gap-1 p-1.5 rounded-md cursor-pointer transition-all border ${config.subtitle_style === s.value ? 'border-accent bg-accent/10' : 'border-border hover:border-border-light hover:bg-bg-hover'}`}
                    onClick={() => !disabled && handleChange('subtitle_style', s.value)}
                  >
                    <div className="w-full h-8 rounded flex items-center justify-center text-sm font-bold overflow-hidden" style={s.preview}>Aa</div>
                    <span className="text-[9px] text-text-secondary">{s.label}</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <Label icon={Palette}>Cores</Label>
              <div className="flex gap-3">
                <div className="flex flex-col items-center gap-1">
                  <div className="w-8 h-8 rounded-md border border-border-light overflow-hidden cursor-pointer">
                    <input type="color" value={config.highlight_color} className="w-10 h-10 -m-1 cursor-pointer"
                      onChange={(e) => handleChange('highlight_color', e.target.value)} disabled={disabled} />
                  </div>
                  <span className="text-[9px] text-text-muted">Destaque</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <div className="w-8 h-8 rounded-md border border-border-light overflow-hidden cursor-pointer">
                    <input type="color" value={config.base_color} className="w-10 h-10 -m-1 cursor-pointer"
                      onChange={(e) => handleChange('base_color', e.target.value)} disabled={disabled} />
                  </div>
                  <span className="text-[9px] text-text-muted">Base</span>
                </div>
              </div>
            </div>

            <div>
              <Label icon={MoveVertical}>Margem Inferior</Label>
              <RangeRow configKey="text_margin_bottom" min={40} max={400} value={config.text_margin_bottom}
                onChange={(v) => handleChange('text_margin_bottom', v)} suffix="px" />
            </div>
          </div>
        </div>
      </div>

      {/* Processing Section */}
      <div className="bg-bg-tertiary border-b border-border overflow-hidden">
        <SectionHeader icon={Sparkles} title="Processamento" collapsed={!sections.processing} onToggle={() => toggleSection('processing')} onReset={() => handleReset('processing')} />
        <div className="overflow-hidden transition-all duration-200" style={{ maxHeight: sections.processing ? '600px' : '0' }}>
          <div className="p-3 flex flex-col gap-3">
            <div>
              <Label icon={Hash}>Max Cortes</Label>
              <RangeRow configKey="max_cuts" min={1} max={20} value={config.max_cuts}
                onChange={(v) => handleChange('max_cuts', v)} />
            </div>
            <div>
              <Label icon={Brain}>Modelo Transcricao</Label>
              <select className="w-full px-2.5 py-1.5 bg-bg-elevated border border-border rounded-md text-xs text-text outline-none focus:border-accent cursor-pointer transition-colors"
                value={config.whisper_model}
                onChange={(e) => handleChange('whisper_model', e.target.value)} disabled={disabled}>
                <option value="parakeet">Parakeet TDT (recomendado)</option>
                <option value="small">Whisper Small</option>
                <option value="medium">Whisper Medium (lento)</option>
                <option value="large">Whisper Large (mais lento)</option>
              </select>
            </div>
            <div>
              <Label icon={ScanSearch}>Deteccao</Label>
              <select className="w-full px-2.5 py-1.5 bg-bg-elevated border border-border rounded-md text-xs text-text outline-none focus:border-accent cursor-pointer transition-colors"
                value={config.detect_method}
                onChange={(e) => handleChange('detect_method', e.target.value)} disabled={disabled}>
                <option value="ia">IA (Ollama/OpenAI)</option>
                <option value="heuristicas">Heuristicas</option>
                <option value="ambos">Ambos</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Effects Section */}
      <div className="bg-bg-tertiary overflow-hidden">
        <SectionHeader icon={SlidersHorizontal} title="Efeitos" collapsed={!sections.effects} onToggle={() => toggleSection('effects')} onReset={() => handleReset('effects')} />
        <div className="overflow-hidden transition-all duration-200" style={{ maxHeight: sections.effects ? '600px' : '0' }}>
          <div className="p-3 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <Label icon={Crop}>Crop Vertical (9:16)</Label>
              <div
                className={`w-8 h-4 rounded-full cursor-pointer transition-all ${config.crop_vertical ? 'bg-accent' : 'bg-bg-elevated border border-border'}`}
                onClick={() => !disabled && handleChange('crop_vertical', !config.crop_vertical)}
              >
                <div className={`w-3 h-3 bg-white rounded-full m-0.5 transition-transform ${config.crop_vertical ? 'translate-x-4' : ''}`} />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <Label icon={ZoomIn}>Zoom Dinamico</Label>
              <div
                className={`w-8 h-4 rounded-full cursor-pointer transition-all ${config.zoom_dinamico ? 'bg-accent' : 'bg-bg-elevated border border-border'}`}
                onClick={() => !disabled && handleChange('zoom_dinamico', !config.zoom_dinamico)}
              >
                <div className={`w-3 h-3 bg-white rounded-full m-0.5 transition-transform ${config.zoom_dinamico ? 'translate-x-4' : ''}`} />
              </div>
            </div>

            <div>
              <Label icon={Timer}>Fade In/Out</Label>
              <div className="flex items-center gap-2">
                <input type="range" className="flex-1 cursor-pointer accent-accent" min={0} max={15}
                  value={Math.round((config.fade_transition || 0) * 10)}
                  onChange={(e) => handleChange('fade_transition', parseInt(e.target.value) / 10)} disabled={disabled} />
                <span className="text-[11px] text-text-secondary w-10 text-right">{(config.fade_transition || 0).toFixed(1)}s</span>
              </div>
            </div>

            <div>
              <Label icon={Volume2}>Volume Musica</Label>
              <div className="flex items-center gap-2">
                <input type="range" className="flex-1 cursor-pointer accent-accent" min={0} max={50}
                  value={Math.round(config.bg_music_volume * 100)}
                  onChange={(e) => handleChange('bg_music_volume', parseInt(e.target.value) / 100)} disabled={disabled} />
                <span className="text-[11px] text-text-secondary w-10 text-right">{Math.round(config.bg_music_volume * 100)}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
