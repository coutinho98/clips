import { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react'
import ConfigPanel from './components/ConfigPanel'
import ProcessingPanel from './components/ProcessingPanel'
import CutsPanel from './components/CutsPanel'
import CommandPalette from './components/CommandPalette'
const VideoEditor = lazy(() => import('./components/VideoEditor'))
import {
  Zap, Loader2, Scissors, Tv, PanelLeftClose, PanelLeftOpen,
  Film, MonitorPlay, Download, ChevronDown,
  RotateCcw, Check, AlertCircle, Info, Command,
} from 'lucide-react'

const PIPELINE_STEPS = [
  { key: 'download', label: 'Download' },
  { key: 'transcribe', label: 'Transcricao' },
  { key: 'detect', label: 'Deteccao' },
  { key: 'cut', label: 'Cortes' },
  { key: 'render', label: 'Render' },
]

function Toast({ toast, onRemove }) {
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => {
      setLeaving(true)
      setTimeout(() => onRemove(toast.id), 300)
    }, toast.duration || 3000)
    return () => clearTimeout(t)
  }, [toast.id, toast.duration, onRemove])

  const icons = { success: Check, error: AlertCircle, info: Info }
  const colors = { success: 'text-success', error: 'text-danger', info: 'text-info' }
  const Icon = icons[toast.type] || Info

  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs border shadow-lg transition-all ${toast.type === 'success' ? 'bg-success/10 border-success/30 text-text' : toast.type === 'error' ? 'bg-danger/10 border-danger/30 text-text' : 'bg-info/10 border-info/30 text-text'} ${leaving ? 'opacity-0 translate-x-4' : ''}`}
      style={{ animation: 'slide-in-right 0.25s ease forwards' }}>
      <Icon size={14} className={colors[toast.type] || 'text-info'} />
      <span>{toast.message}</span>
    </div>
  )
}

function getPipelineState(step, progress) {
  const steps = PIPELINE_STEPS.map(s => ({ ...s, status: 'pending' }))
  if (!step && !progress) return steps
  if (progress >= 100) return steps.map(s => ({ ...s, status: 'done' }))

  const lower = (step || '').toLowerCase()
  const stepOrder = ['download', 'transcribe', 'detect', 'cut', 'render']

  let activeIdx = -1
  if (lower.includes('baixando') || lower.includes('download') || lower.includes('enviando')) activeIdx = 0
  else if (lower.includes('transcri') || lower.includes('whisper') || lower.includes('parakeet')) activeIdx = 1
  else if (lower.includes('detect') || lower.includes('highlight') || lower.includes('ia ')) activeIdx = 2
  else if (lower.includes('cort') || lower.includes('extraindo') || lower.includes('refin')) activeIdx = 3
  else if (lower.includes('render') || lower.includes('legenda') || lower.includes('gerando') || lower.includes('aplicando')) activeIdx = 4
  else if (lower.includes('iniciando')) activeIdx = 0

  if (activeIdx >= 0) {
    for (let i = 0; i < activeIdx; i++) steps[i].status = 'done'
    steps[activeIdx].status = 'active'
  }

  return steps
}

export default function App() {
  const [config, setConfig] = useState(null)
  const [defaults, setDefaults] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [step, setStep] = useState('')
  const [cuts, setCuts] = useState([])
  const [error, setError] = useState('')
  const [editingCut, setEditingCut] = useState(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [sidebarVisible, setSidebarVisible] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(288)
  const [activeMainTab, setActiveMainTab] = useState('import')
  const [toasts, setToasts] = useState([])
  const [menuOpen, setMenuOpen] = useState(null)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [showCommand, setShowCommand] = useState(false)
  const [showSplash, setShowSplash] = useState(true)
  const wsRef = useRef(null)
  const resizeRef = useRef(null)
  const toastsIdRef = useRef(0)
  const prevProcessingRef = useRef(false)

  const addToast = useCallback((message, type = 'info') => {
    const id = ++toastsIdRef.current
    setToasts(prev => [...prev, { id, message, type }])
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  useEffect(() => {
    fetchConfig()
    fetchExistingCuts()
    connectWS()
    return () => wsRef.current?.close()
  }, [])

  useEffect(() => {
    if (!processing) return
    const interval = setInterval(async () => {
      try {
        const res = await fetch('/api/status')
        const data = await res.json()
        if (!data.processing) {
          setProcessing(false)
          setProgress(0)
          setStep('')
        } else {
          setProgress(data.progress)
          setStep(data.step)
        }
      } catch {}
    }, 3000)
    return () => clearInterval(interval)
  }, [processing])

  useEffect(() => {
    if (prevProcessingRef.current && !processing && cuts.length > 0) {
      addToast('Processamento concluido! ' + cuts.length + ' cortes gerados.', 'success')
    }
    prevProcessingRef.current = processing
  }, [processing, cuts.length, addToast])

  useEffect(() => {
    function handleClick(e) {
      if (!e.target.closest('.topbar-menus')) setMenuOpen(null)
    }
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [])

  useEffect(() => {
    function handleKeyDown(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setShowCommand(v => !v)
        return
      }
      if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault()
        setShowShortcuts(v => !v)
        return
      }
      if (e.key === 'Escape') {
        setShowShortcuts(false)
        setShowCommand(false)
        return
      }
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return
      if (e.key === '1') setActiveMainTab('import')
      if (e.key === '2') setActiveMainTab('cuts')
      if (e.key === '3' && editingCut) setActiveMainTab('editor')
      if (e.key === 'b' || e.key === 'B') setSidebarVisible(v => !v)
      if (e.key === '?') setShowShortcuts(true)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [editingCut])

  function handleSidebarResize(e) {
    const startX = e.clientX
    const startW = sidebarWidth
    function onMove(ev) {
      const delta = ev.clientX - startX
      setSidebarWidth(Math.max(220, Math.min(450, startW + delta)))
    }
    function onUp() {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      if (resizeRef.current) resizeRef.current.classList.remove('bg-accent')
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    if (resizeRef.current) resizeRef.current.classList.add('bg-accent')
  }

  async function fetchExistingCuts() {
    try {
      const res = await fetch('/api/cuts')
      const data = await res.json()
      if (data.cuts?.length > 0 && cuts.length === 0) {
        const existing = data.cuts.map(c => ({
          ...c,
          cut_id: c.cut_id || c.arquivo,
          _new: false,
        }))
        setCuts(existing)
      }
    } catch {}
  }

  function connectWS() {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws`)
    ws.onopen = () => setWsConnected(true)
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'progress') {
        setProgress(data.progress)
        setStep(data.step)
        if (data.error) {
          setError(data.error)
          addToast(data.error, 'error')
        }
        if (data.cuts) {
          setCuts(data.cuts.map(c => ({ ...c, _new: true })))
          if (data.progress >= 100 && data.cuts.length > 0) setActiveMainTab('cuts')
        }
        if (data.rerendered) {
          setCuts(prev => {
            const idx = prev.findIndex(c => c.cut_id === data.rerendered.cut_id)
            if (idx >= 0) {
              const updated = [...prev]
              updated[idx] = { ...updated[idx], ...data.rerendered }
              return updated
            }
            return prev
          })
          setEditingCut(null)
          setActiveMainTab('cuts')
          addToast('Re-renderizacao concluida!', 'success')
        }
        if (data.progress >= 100) {
          setProcessing(false)
        }
      }
    }
    ws.onclose = () => {
      setWsConnected(false)
      setTimeout(connectWS, 2000)
    }
    wsRef.current = ws
  }

  const fetchConfig = useCallback(async () => {
    const res = await fetch('/api/config')
    const data = await res.json()
    setConfig(data.config)
    setDefaults(data.defaults)
  }, [])

  const updateConfig = useCallback(async (newConfig) => {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig),
    })
    const data = await res.json()
    setConfig(data.config)
  }, [])

  const startProcess = useCallback(async (url, localPath) => {
    setError('')
    setProcessing(true)
    setProgress(0)
    setStep('Iniciando...')
    setCuts([])
    setEditingCut(null)

    const formData = new FormData()
    if (url) formData.append('url', url)
    if (localPath) formData.append('local_path', localPath)

    const res = await fetch('/api/process', {
      method: 'POST',
      body: formData,
    })
    const data = await res.json()
    if (data.status === 'error') {
      setError(data.message)
      setProcessing(false)
      addToast(data.message, 'error')
    }
    if (data.status === 'already_processing') {
      setError('Ja existe um processamento rodando')
      setProcessing(true)
    }
    if (data.config) setConfig(data.config)
  }, [addToast])

  const uploadVideo = useCallback(async (file) => {
    setError('')
    setProcessing(true)
    setProgress(0)
    setStep('Enviando video...')
    setCuts([])
    setEditingCut(null)

    const formData = new FormData()
    formData.append('video', file)

    const res = await fetch('/api/process', {
      method: 'POST',
      body: formData,
    })
    const data = await res.json()
    if (data.error) {
      setError(data.error)
      setProcessing(false)
      addToast(data.error, 'error')
    }
  }, [addToast])

  const handleRerender = useCallback(async (editConfig) => {
    if (!editingCut?.cut_id) return
    setProcessing(true)
    setProgress(0)
    setStep('Re-renderizando...')

    const res = await fetch(`/api/cut/${encodeURIComponent(editingCut.cut_id)}/rerender`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editConfig),
    })
    const data = await res.json()
    if (data.error) {
      setError(data.error)
      setProcessing(false)
      addToast(data.error, 'error')
    }
  }, [editingCut, addToast])

  const handleEditCut = useCallback((cut) => {
    setEditingCut(cut)
    setActiveMainTab('editor')
  }, [])

  const handleCancelProcess = useCallback(() => {
    setProcessing(false)
    setProgress(0)
    setStep('')
    addToast('Processamento cancelado', 'info')
  }, [addToast])

  const pipeline = getPipelineState(step, progress)

  useEffect(() => {
    const t = setTimeout(() => setShowSplash(false), 2600)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className="flex flex-col h-screen bg-bg text-text">
      {/* Splash */}
      {showSplash && (
        <div className="fixed inset-0 z-[2000] bg-black flex items-center justify-center cursor-pointer" style={{ animation: 'splash-fade-out 0.4s ease 2.2s forwards' }} onClick={() => setShowSplash(false)}>
          <div className="flex flex-col items-center gap-4">
            <div className="text-4xl font-bold tracking-tight flex">
              {'FALA TU'.split('').map((ch, i) => (
                <span key={i} className="inline-block opacity-0" style={{ animation: `splash-char-in 0.5s ease ${i * 0.08}s forwards` }}>
                  {ch === ' ' ? '\u00A0' : ch}
                </span>
              ))}
            </div>
            <div className="text-xs text-zinc-500 opacity-0" style={{ animation: 'splash-fade-in 0.5s ease 0.6s forwards' }}>clips que falam por si</div>
            <div className="w-0 h-0.5 bg-accent rounded-full overflow-hidden" style={{ animation: 'splash-bar 1.5s ease 0.4s forwards' }} />
          </div>
        </div>
      )}

      {/* Topbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-bg-secondary shrink-0 z-50">
        <div className="flex items-center gap-2">
          <button className="flex items-center justify-center w-8 h-8 rounded-md text-text-secondary hover:text-text hover:bg-bg-hover transition-all" onClick={() => setSidebarVisible(v => !v)} title="Toggle Sidebar (B)">
            {sidebarVisible ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
          </button>
          <div className="flex items-center gap-2 mr-2">
            <div className="flex items-center justify-center w-7 h-7 rounded-md bg-accent"><Zap size={16} className="text-white" /></div>
            <h1 className="text-sm font-bold text-text">Fala Tu</h1>
          </div>
          <div className="topbar-menus flex items-center gap-0.5">
            {[
              { key: 'file', label: 'Arquivo', items: [
                { label: 'Importar Video', shortcut: '1', action: () => { setActiveMainTab('import'); setMenuOpen(null) } },
                { divider: true },
                { label: 'Recarregar Config', action: () => { fetchConfig(); setMenuOpen(null) } },
              ]},
              { key: 'edit', label: 'Editar', items: [
                { label: 'Toggle Sidebar', shortcut: 'B', action: () => { setSidebarVisible(v => !v); setMenuOpen(null) } },
                { label: 'Command Palette', shortcut: 'Ctrl+K', action: () => { setShowCommand(true); setMenuOpen(null) } },
                { divider: true },
                { label: 'Resetar Config', action: () => { if (defaults) { updateConfig(defaults); setMenuOpen(null) } } },
              ]},
              { key: 'help', label: 'Ajuda', items: [
                { label: 'Atalhos de Teclado', shortcut: 'Ctrl+/', action: () => { setShowShortcuts(true); setMenuOpen(null) } },
              ]},
            ].map(menu => (
              <div key={menu.key} className="relative">
                <button
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${menuOpen === menu.key ? 'bg-bg-hover text-text' : 'text-text-secondary hover:text-text hover:bg-bg-hover'}`}
                  onClick={() => setMenuOpen(menuOpen === menu.key ? null : menu.key)}
                >
                  {menu.label}
                </button>
                {menuOpen === menu.key && (
                  <div className="absolute top-full left-0 mt-1 bg-bg-secondary border border-border-light rounded-lg shadow-2xl py-1 min-w-[180px] z-[100]" style={{ animation: 'modal-slide 150ms ease' }}>
                    {menu.items.map((item, i) => item.divider ? (
                      <div key={i} className="h-px bg-border my-1" />
                    ) : (
                      <div key={i} className="flex items-center justify-between px-3 py-1.5 text-xs text-text-secondary hover:text-text hover:bg-bg-hover cursor-pointer transition-colors"
                        onClick={item.action}>
                        <span>{item.label}</span>
                        {item.shortcut && <kbd className="text-[9px] text-text-muted bg-bg-elevated px-1.5 py-0.5 rounded">{item.shortcut}</kbd>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button className="flex items-center gap-2 px-3 py-1 bg-bg-elevated border border-border rounded-md text-[11px] text-text-muted hover:border-border-light transition-all" onClick={() => setShowCommand(true)} title="Command Palette (Ctrl+K)">
            <Command size={12} />
            <span>Buscar...</span>
            <kbd className="text-[9px] text-text-muted bg-bg px-1.5 py-0.5 rounded border border-border">Ctrl K</kbd>
          </button>
          {processing && (
            <div className="flex items-center gap-1.5 px-2 py-1 bg-accent/10 rounded-md text-[11px] text-accent-light">
              <Loader2 size={12} className="animate-spin" />
              <span className="max-w-[120px] truncate">{step || 'Processando...'}</span>
            </div>
          )}
          <div className="flex items-center gap-1.5 px-2 py-1">
            <div className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-success animate-pulse' : 'bg-danger'}`} />
            <span className="text-[10px] text-text-muted">{wsConnected ? 'Online' : 'Offline'}</span>
          </div>
        </div>
      </div>

      {/* Workspace */}
      <div className="flex flex-1 overflow-hidden">
        {sidebarVisible && (
          <>
            <div className="overflow-y-auto border-r border-border bg-bg-secondary" style={{ width: sidebarWidth }}>
              <ConfigPanel
                config={config}
                defaults={defaults}
                onUpdate={updateConfig}
                disabled={processing}
              />
            </div>
            <div
              ref={resizeRef}
              className="w-1 cursor-col-resize hover:bg-accent transition-colors shrink-0"
              onMouseDown={handleSidebarResize}
            />
          </>
        )}

        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Tabs */}
          <div className="flex items-center px-2 h-9 border-b border-border bg-bg-secondary shrink-0 gap-0.5">
            {[
              { key: 'import', label: 'Importar', icon: Film, badge: null },
              { key: 'cuts', label: 'Cortes', icon: Scissors, badge: cuts.length > 0 ? cuts.length : null },
              ...(editingCut ? [{ key: 'editor', label: 'Editor', icon: MonitorPlay, badge: null }] : []),
            ].map(tab => (
              <button
                key={tab.key}
                className={`relative flex items-center gap-1.5 px-3.5 h-[30px] text-xs font-medium transition-colors ${activeMainTab === tab.key ? 'text-text bg-bg-tertiary rounded-t-md' : 'text-text-muted hover:text-text-secondary'}`}
                onClick={() => setActiveMainTab(tab.key)}
              >
                <tab.icon size={13} className={activeMainTab === tab.key ? 'text-accent-light' : ''} />
                {tab.label}
                {tab.badge !== null && (
                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded min-w-[16px] text-center leading-none ${activeMainTab === tab.key ? 'bg-accent text-white' : 'bg-bg-elevated text-text-muted'}`}>{tab.badge}</span>
                )}
                {activeMainTab === tab.key && (
                  <div className="absolute -bottom-px left-0 right-0 h-0.5 bg-accent rounded-full" />
                )}
              </button>
            ))}
            {editingCut && (
              <button
                className="ml-auto flex items-center justify-center w-6 h-6 rounded text-text-muted hover:text-danger hover:bg-danger/10 transition-colors text-xs"
                onClick={() => { setEditingCut(null); setActiveMainTab('cuts') }}
                title="Fechar editor"
              >
                ×
              </button>
            )}
          </div>

          {/* Main body */}
          <div className="flex-1 overflow-hidden">
            {activeMainTab === 'import' && (
              <div className="h-full overflow-y-auto p-4 bg-bg">
                <div className="max-w-2xl mx-auto">
                <ProcessingPanel
                  onStart={startProcess}
                  onUpload={uploadVideo}
                  processing={processing}
                  progress={progress}
                  step={step}
                  error={error}
                  pipeline={pipeline}
                  onCancel={handleCancelProcess}
                />
                </div>
              </div>
            )}

            {activeMainTab === 'cuts' && (
              <CutsPanel
                cuts={cuts}
                onEdit={handleEditCut}
                onGoImport={() => setActiveMainTab('import')}
              />
            )}

            {activeMainTab === 'editor' && editingCut && (
              <div className="h-full p-1.5">
              <Suspense fallback={<div className="flex items-center justify-center h-full text-xs text-text-muted">Carregando editor...</div>}>
                <VideoEditor
                  cut={editingCut}
                  config={config}
                  onRerender={handleRerender}
                  onClose={() => { setEditingCut(null); setActiveMainTab('cuts') }}
                  processing={processing}
                />
              </Suspense>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Statusbar */}
      <div className="flex items-center gap-3 px-3 py-1 border-t border-border bg-bg-secondary text-[10px] text-text-muted shrink-0">
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-success' : 'bg-danger'}`} />
          <span>{wsConnected ? 'WS conectado' : 'Reconectando...'}</span>
        </div>
        <div className="w-px h-3 bg-border" />
        <div className="flex items-center gap-1.5">
          <Scissors size={10} />
          <span>{cuts.length} cortes</span>
        </div>
        <div className="w-px h-3 bg-border" />
        <div className="flex items-center gap-1.5">
          <Tv size={10} />
          <span>{processing ? step || 'Processando...' : 'Pronto'}</span>
        </div>
        <span className="ml-auto">Fala Tu v1.0</span>
      </div>

      {/* Shortcuts modal */}
      {showShortcuts && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[1000] flex items-center justify-center" style={{ animation: 'modal-fade 150ms ease' }} onClick={() => setShowShortcuts(false)}>
          <div className="bg-bg-secondary border border-border-light rounded-xl shadow-2xl w-[90%] max-w-[500px]" style={{ animation: 'modal-slide 200ms ease' }} onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <span className="text-sm font-semibold text-text">Atalhos de Teclado</span>
              <button className="px-2 py-0.5 text-[10px] text-text-muted bg-bg-elevated border border-border rounded hover:text-text" onClick={() => setShowShortcuts(false)}>Esc</button>
            </div>
            <div className="grid grid-cols-2 gap-6 p-4">
              <div>
                <div className="text-[11px] font-bold uppercase tracking-wide text-text-muted mb-2">Navegacao</div>
                {[
                  ['Importar', '1'], ['Cortes', '2'], ['Editor', '3'], ['Toggle Sidebar', 'B'],
                ].map(([label, key]) => (
                  <div key={label} className="flex items-center justify-between py-1 text-xs text-text-secondary">
                    <span>{label}</span><kbd className="text-[9px] bg-bg-elevated border border-border px-1.5 py-0.5 rounded">{key}</kbd>
                  </div>
                ))}
              </div>
              <div>
                <div className="text-[11px] font-bold uppercase tracking-wide text-text-muted mb-2">Ferramentas</div>
                {[
                  ['Command Palette', 'Ctrl K'], ['Atalhos', 'Ctrl /'], ['Fechar modal', 'Esc'],
                ].map(([label, key]) => (
                  <div key={label} className="flex items-center justify-between py-1 text-xs text-text-secondary">
                    <span>{label}</span><kbd className="text-[9px] bg-bg-elevated border border-border px-1.5 py-0.5 rounded">{key}</kbd>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Command palette */}
      {showCommand && (
        <CommandPalette
          cuts={cuts}
          onNavigate={(tab) => { setActiveMainTab(tab); setShowCommand(false) }}
          onEditCut={(cut) => { handleEditCut(cut); setShowCommand(false) }}
          onToggleSidebar={() => { setSidebarVisible(v => !v); setShowCommand(false) }}
          onShowShortcuts={() => { setShowShortcuts(true); setShowCommand(false) }}
          onClose={() => setShowCommand(false)}
        />
      )}

      {/* Toasts */}
      <div className="fixed bottom-8 right-4 z-[999] flex flex-col gap-2">
        {toasts.map(t => (
          <Toast key={t.id} toast={t} onRemove={removeToast} />
        ))}
      </div>
    </div>
  )
}
