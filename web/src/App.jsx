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
import './App.css'

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
  const Icon = icons[toast.type] || Info

  return (
    <div className={`toast ${toast.type} ${leaving ? 'leaving' : ''}`}>
      <Icon className="toast-icon" />
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
      if (resizeRef.current) resizeRef.current.classList.remove('active')
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    if (resizeRef.current) resizeRef.current.classList.add('active')
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

  return (
    <div className="app">
      <div className="topbar">
        <div className="topbar-left">
          <button className="sidebar-toggle-btn" onClick={() => setSidebarVisible(v => !v)} title="Toggle Sidebar (B)">
            {sidebarVisible ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
          </button>
          <div className="topbar-brand">
            <div className="topbar-logo"><Zap size={16} /></div>
            <div className="topbar-text">
              <h1>Fala Tu</h1>
            </div>
          </div>
          <div className="topbar-menus">
            <div
              className={`menu-item ${menuOpen === 'file' ? 'open' : ''}`}
              onClick={() => setMenuOpen(menuOpen === 'file' ? null : 'file')}
            >
              Arquivo
              {menuOpen === 'file' && (
                <div className="menu-dropdown">
                  <div className="menu-dropdown-item" onClick={() => { setActiveMainTab('import'); setMenuOpen(null) }}>
                    Importar Video <span className="shortcut">1</span>
                  </div>
                  <div className="menu-dropdown-divider" />
                  <div className="menu-dropdown-item" onClick={() => { fetchConfig(); setMenuOpen(null) }}>
                    Recarregar Config
                  </div>
                </div>
              )}
            </div>
            <div
              className={`menu-item ${menuOpen === 'edit' ? 'open' : ''}`}
              onClick={() => setMenuOpen(menuOpen === 'edit' ? null : 'edit')}
            >
              Editar
              {menuOpen === 'edit' && (
                <div className="menu-dropdown">
                  <div className="menu-dropdown-item" onClick={() => { setSidebarVisible(v => !v); setMenuOpen(null) }}>
                    Toggle Sidebar <span className="shortcut">B</span>
                  </div>
                  <div className="menu-dropdown-item" onClick={() => { setShowCommand(true); setMenuOpen(null) }}>
                    Command Palette <span className="shortcut">Ctrl+K</span>
                  </div>
                  <div className="menu-dropdown-divider" />
                  <div className="menu-dropdown-item" onClick={() => { if (defaults) { updateConfig(defaults); setMenuOpen(null) } }}>
                    Resetar Config
                  </div>
                </div>
              )}
            </div>
            <div
              className={`menu-item ${menuOpen === 'help' ? 'open' : ''}`}
              onClick={() => setMenuOpen(menuOpen === 'help' ? null : 'help')}
            >
              Ajuda
              {menuOpen === 'help' && (
                <div className="menu-dropdown">
                  <div className="menu-dropdown-item" onClick={() => { setShowShortcuts(true); setMenuOpen(null) }}>
                    Atalhos de Teclado <span className="shortcut">Ctrl+/</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="topbar-right">
          <button className="topbar-cmd-btn" onClick={() => setShowCommand(true)} title="Command Palette (Ctrl+K)">
            <Command size={12} />
            <span>Buscar...</span>
            <kbd className="topbar-cmd-kbd">Ctrl K</kbd>
          </button>
          {processing && (
            <div className="topbar-processing">
              <Loader2 size={12} className="spin" />
              {step || 'Processando...'}
            </div>
          )}
          <div className="topbar-connection">
            <div className={`connection-dot ${wsConnected ? '' : 'off'}`} />
            <span>{wsConnected ? 'Online' : 'Offline'}</span>
          </div>
        </div>
      </div>

      <div className="workspace">
        {sidebarVisible && (
          <>
            <div className="sidebar" style={{ width: sidebarWidth }}>
              <ConfigPanel
                config={config}
                defaults={defaults}
                onUpdate={updateConfig}
                disabled={processing}
              />
            </div>
            <div
              ref={resizeRef}
              className="sidebar-resize-handle"
              onMouseDown={handleSidebarResize}
            />
          </>
        )}

        <div className="main-content">
          <div className="main-tabs">
            <button
              className={`main-tab ${activeMainTab === 'import' ? 'active' : ''}`}
              onClick={() => setActiveMainTab('import')}
            >
              <Film className="main-tab-icon" /> Importar
            </button>
            <button
              className={`main-tab ${activeMainTab === 'cuts' ? 'active' : ''}`}
              onClick={() => setActiveMainTab('cuts')}
            >
              <Scissors className="main-tab-icon" /> Cortes
              {cuts.length > 0 && <span className="main-tab-badge">{cuts.length}</span>}
            </button>
            {editingCut && (
              <button
                className={`main-tab ${activeMainTab === 'editor' ? 'active' : ''}`}
                onClick={() => setActiveMainTab('editor')}
              >
                <MonitorPlay className="main-tab-icon" /> Editor
              </button>
            )}
          </div>

          <div className="main-body">
            {activeMainTab === 'import' && (
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
            )}

            {activeMainTab === 'cuts' && (
              <CutsPanel
                cuts={cuts}
                onEdit={handleEditCut}
                onGoImport={() => setActiveMainTab('import')}
              />
            )}

            {activeMainTab === 'editor' && editingCut && (
              <Suspense fallback={<div className="editor-preview-placeholder">Carregando editor...</div>}>
              <VideoEditor
                cut={editingCut}
                config={config}
                onRerender={handleRerender}
                onClose={() => { setEditingCut(null); setActiveMainTab('cuts') }}
                processing={processing}
              />
              </Suspense>
            )}
          </div>
        </div>
      </div>

      <div className="statusbar">
        <div className="statusbar-item">
          <div className={`connection-dot ${wsConnected ? '' : 'off'}`} />
          <span>{wsConnected ? 'WS conectado' : 'Reconectando...'}</span>
        </div>
        <div className="statusbar-divider" />
        <div className="statusbar-item">
          <Scissors size={10} />
          <span>{cuts.length} cortes</span>
        </div>
        <div className="statusbar-divider" />
        <div className="statusbar-item">
          <Tv size={10} />
          <span>{processing ? step || 'Processando...' : 'Pronto'}</span>
        </div>
        <span className="statusbar-right">Fala Tu v1.0</span>
      </div>

      {showShortcuts && (
        <div className="modal-overlay" onClick={() => setShowShortcuts(false)}>
          <div className="modal-content shortcuts-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">Atalhos de Teclado</span>
              <button className="modal-close" onClick={() => setShowShortcuts(false)}>Esc</button>
            </div>
            <div className="shortcuts-grid">
              <div className="shortcut-category">
                <div className="shortcut-category-title">Navegacao</div>
                <div className="shortcut-row"><span>Importar</span><kbd>1</kbd></div>
                <div className="shortcut-row"><span>Cortes</span><kbd>2</kbd></div>
                <div className="shortcut-row"><span>Editor</span><kbd>3</kbd></div>
                <div className="shortcut-row"><span>Toggle Sidebar</span><kbd>B</kbd></div>
              </div>
              <div className="shortcut-category">
                <div className="shortcut-category-title">Ferramentas</div>
                <div className="shortcut-row"><span>Command Palette</span><kbd>Ctrl K</kbd></div>
                <div className="shortcut-row"><span>Atalhos</span><kbd>Ctrl /</kbd></div>
                <div className="shortcut-row"><span>Fechar modal</span><kbd>Esc</kbd></div>
              </div>
            </div>
          </div>
        </div>
      )}

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

      <div className="toast-container">
        {toasts.map(t => (
          <Toast key={t.id} toast={t} onRemove={removeToast} />
        ))}
      </div>
    </div>
  )
}
