import { useState, useEffect, useRef } from 'react'

export default function ProcessingPanel({ onStart, onUpload, processing, progress, step, error }) {
  const urlRef = useRef('')
  const fileRef = useRef(null)
  const [localVideos, setLocalVideos] = useState([])
  const [selectedVideo, setSelectedVideo] = useState('')

  useEffect(() => {
    fetchLocalVideos()
  }, [])

  async function fetchLocalVideos() {
    try {
      const res = await fetch('/api/videos')
      const data = await res.json()
      setLocalVideos(data.videos || [])
    } catch {}
  }

  function handleSubmit() {
    const url = urlRef.current?.trim()
    if (!url) return
    onStart(url)
  }

  function handleLocalProcess() {
    if (!selectedVideo) return
    onStart(null, selectedVideo)
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (file) onUpload(file)
  }

  return (
    <div className="card">
      <h2>Processar Video</h2>

      <div className="form-group">
        <label>Video Local (ja baixado)</label>
        <div style={{ display: 'flex', gap: 8 }}>
          <select
            value={selectedVideo}
            onChange={(e) => setSelectedVideo(e.target.value)}
            disabled={processing}
            style={{ flex: 1 }}
          >
            <option value="">Selecione um video...</option>
            {localVideos.map((v) => (
              <option key={v.arquivo} value={v.caminho}>
                {v.arquivo} ({v.tamanho_mb} MB)
              </option>
            ))}
          </select>
          <button
            className="btn btn-primary"
            onClick={handleLocalProcess}
            disabled={processing || !selectedVideo}
            style={{ width: 'auto', whiteSpace: 'nowrap' }}
          >
            Processar
          </button>
        </div>
      </div>

      <hr className="divider" />

      <div className="form-group">
        <label>URL da Live (YouTube, Twitch, etc)</label>
        <div className="url-row">
          <input
            type="text"
            placeholder="https://www.youtube.com/watch?v=..."
            onChange={(e) => urlRef.current = e.target.value}
            disabled={processing}
          />
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={processing}
            style={{ width: 'auto', whiteSpace: 'nowrap' }}
          >
            Baixar
          </button>
        </div>
      </div>

      <div className="form-group">
        <label>Ou envie um arquivo de video</label>
        <div
          className="upload-zone"
          onClick={() => fileRef.current?.click()}
        >
          Clique para selecionar um video
          <input
            ref={fileRef}
            type="file"
            accept="video/*"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
        </div>
      </div>

      {(processing || progress > 0) && (
        <div className="progress-section">
          <div className="progress-step">{step}</div>
          <div className="progress-bar-bg">
            <div
              className="progress-bar-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="progress-pct">{Math.round(progress)}%</div>
        </div>
      )}

      {error && <div className="error-msg">{error}</div>}
    </div>
  )
}
