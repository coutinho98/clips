import { useState, useEffect, useRef } from 'react'
import ConfigPanel from './components/ConfigPanel'
import ProcessingPanel from './components/ProcessingPanel'
import CutsPanel from './components/CutsPanel'
import VideoEditor from './components/VideoEditor'
import './App.css'

function App() {
  const [config, setConfig] = useState(null)
  const [defaults, setDefaults] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [step, setStep] = useState('')
  const [cuts, setCuts] = useState([])
  const [error, setError] = useState('')
  const [editingCut, setEditingCut] = useState(null)
  const wsRef = useRef(null)

  useEffect(() => {
    fetchConfig()
    fetchExistingCuts()
    connectWS()
    return () => wsRef.current?.close()
  }, [])

  async function fetchExistingCuts() {
    try {
      const res = await fetch('/api/cuts')
      const data = await res.json()
      if (data.cuts?.length > 0 && cuts.length === 0) {
        const existing = data.cuts.map(c => ({
          ...c,
          cut_id: c.cut_id || c.arquivo,
        }))
        setCuts(existing)
      }
    } catch {}
  }

  function connectWS() {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws`)
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'progress') {
        setProgress(data.progress)
        setStep(data.step)
        if (data.error) setError(data.error)
        if (data.cuts) setCuts(data.cuts)
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
        }
        if (data.progress >= 100) {
          setProcessing(false)
        }
      }
    }
    ws.onclose = () => setTimeout(connectWS, 2000)
    wsRef.current = ws
  }

  async function fetchConfig() {
    const res = await fetch('/api/config')
    const data = await res.json()
    setConfig(data.config)
    setDefaults(data.defaults)
  }

  async function updateConfig(newConfig) {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig),
    })
    const data = await res.json()
    setConfig(data.config)
  }

  async function startProcess(url, localPath) {
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
    }
    if (data.status === 'already_processing') {
      setError('Ja existe um processamento rodando')
      setProcessing(true)
    }
    if (data.config) setConfig(data.config)
  }

  async function uploadVideo(file) {
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
    }
  }

  async function handleRerender(editConfig) {
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
    }
  }

  function handleEditCut(cut) {
    setEditingCut(cut)
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Dark Channel Bot</h1>
        <span className="subtitle">Cortes automaticos para Reels</span>
      </header>

      <div className="main-grid">
        <div className="left-col">
          <ConfigPanel
            config={config}
            defaults={defaults}
            onUpdate={updateConfig}
            disabled={processing}
          />
        </div>

        <div className="right-col">
          <ProcessingPanel
            onStart={startProcess}
            onUpload={uploadVideo}
            processing={processing}
            progress={progress}
            step={step}
            error={error}
          />

          {editingCut ? (
            <VideoEditor
              cut={editingCut}
              config={config}
              onRerender={handleRerender}
              onClose={() => setEditingCut(null)}
              processing={processing}
            />
          ) : (
            <CutsPanel cuts={cuts} onEdit={handleEditCut} />
          )}
        </div>
      </div>
    </div>
  )
}

export default App
