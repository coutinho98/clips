import { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react'
import ConfigPanel from './components/ConfigPanel'
import ProcessingPanel from './components/ProcessingPanel'
import CutsPanel from './components/CutsPanel'
const VideoEditor = lazy(() => import('./components/VideoEditor'))
import {
  Zap, Loader2, Scissors, Tv, PanelLeftClose, PanelLeftOpen,
  Film, ScissorsIcon, MonitorPlay, Download, ChevronDown,
  RotateCcw, Check, AlertCircle, Info,
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

function getPipelineState(step) {
  if (!step) return PIPELINE_STEPS.map(s => ({ ...s, status: 'pending' }))
  const lower = step.toLowerCase()
  return PIPELINE_STEPS.map(s => {
    const isActive = lower.includes(s.key) || (s.key === 'render' && lower.includes('render'))
    return { ...s, status: isActive ? 'active' : 'pending' }
  })
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
  const [workspace, setWorkspace] = useState('edit')
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
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return
      if (e.key === '1') setActiveMainTab('import')
      if (e.key === '2') setActiveMainTab('cuts')
      if (e.key === '3' && editingCut) setActiveMainTab('editor')
      if (e.key === 'b' || e.key === 'B') setSidebarVisible(v => !v)
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

  const pipeline = getPipelineState(step)

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
                  <div className="menu-dropdown-item" onClick={() => { addToast('1=Importar  2=Cortes  3=Editor  B=Sidebar', 'info'); setMenuOpen(null) }}>
                    Atalhos de Teclado <span className="shortcut">?</span>
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="workspace-switcher">
            <button className={`ws-btn ${workspace === 'import' ? 'active' : ''}`} onClick={() => { setWorkspace('import'); setActiveMainTab('import') }}>
              <Film className="ws-btn-icon" /> Importar
            </button>
            <button className={`ws-btn ${workspace === 'edit' ? 'active' : ''}`} onClick={() => { setWorkspace('edit'); setActiveMainTab('cuts') }}>
              <Scissors className="ws-btn-icon" /> Editar
            </button>
            <button className={`ws-btn ${workspace === 'review' ? 'active' : ''}`} onClick={() => { setWorkspace('review'); setActiveMainTab('cuts') }}>
              <MonitorPlay className="ws-btn-icon" /> Revisar
            </button>
          </div>
        </div>

        <div className="topbar-right">
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

      <div className="toast-container">
        {toasts.map(t => (
          <Toast key={t.id} toast={t} onRemove={removeToast} />
        ))}
      </div>
    </div>
  )
}
