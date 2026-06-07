import { useState } from 'react'

export default function CutsPanel({ cuts, onEdit }) {
  const [playingUrl, setPlayingUrl] = useState(null)

  function getStreamUrl(filename) {
    return `/api/cuts/${filename}`
  }

  function handlePlay(cut) {
    const url = getStreamUrl(cut.arquivo)
    setPlayingUrl(playingUrl === url ? null : url)
  }

  function handleDownload(cut) {
    const a = document.createElement('a')
    a.href = `/api/cuts/${cut.arquivo}/download`
    a.download = cut.arquivo
    a.click()
  }

  if (!cuts || cuts.length === 0) {
    return (
      <div className="card">
        <h2>Cortes Gerados</h2>
        <div className="empty-state">
          Nenhum corte gerado ainda. Processe um video para comecar.
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h2>Cortes Gerados ({cuts.length})</h2>

      <div className="cuts-list">
        {cuts.map((cut, i) => (
          <div key={i}>
            <div className="cut-item">
              <div className="cut-score">
                {cut.score ? `${cut.score}` : '?'}
              </div>
              <div className="cut-info">
                <div className="cut-title">{cut.titulo}</div>
                <div className="cut-meta">
                  {cut.duracao ? `${Math.round(cut.duracao)}s` : ''} 
                  {cut.tamanho_mb ? ` - ${cut.tamanho_mb} MB` : ''}
                </div>
              </div>
              <div className="cut-actions">
                <button
                  className="btn-icon play-btn"
                  onClick={() => handlePlay(cut)}
                  title="Preview"
                >
                  {playingUrl === getStreamUrl(cut.arquivo) ? '■' : '▶'}
                </button>
                <button
                  className="btn-icon"
                  onClick={() => onEdit(cut)}
                  title="Editar legenda"
                  style={{ fontSize: 14 }}
                >
                  ✎
                </button>
                <button
                  className="btn-icon"
                  onClick={() => handleDownload(cut)}
                  title="Download"
                >
                  ↓
                </button>
              </div>
            </div>

            {playingUrl === getStreamUrl(cut.arquivo) && (
              <div className="video-player">
                <video
                  src={playingUrl}
                  controls
                  autoPlay
                  onEnded={() => setPlayingUrl(null)}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
