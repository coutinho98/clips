import { useState } from 'react'
import {
  Play,
  Square,
  Pencil,
  Download,
  Scissors,
  Clock,
  HardDrive,
  Film,
} from 'lucide-react'

export default function CutsPanel({ cuts, onEdit }) {
  const [playingId, setPlayingId] = useState(null)

  function getStreamUrl(filename) {
    return `/api/cuts/${filename}`
  }

  function handlePlay(cut) {
    setPlayingId(playingId === cut.arquivo ? null : cut.arquivo)
  }

  function handleDownload(cut) {
    const a = document.createElement('a')
    a.href = `/api/cuts/${cut.arquivo}/download`
    a.download = cut.arquivo
    a.click()
  }

  if (!cuts || cuts.length === 0) {
    return (
      <div className="panel">
        <div className="panel-header">
          <div className="panel-header-left">
            <Scissors className="panel-icon" />
            <span className="panel-title">Cortes Gerados</span>
          </div>
        </div>
        <div className="empty-state">
          <Film className="empty-state-icon" />
          <div className="empty-state-title">Nenhum corte gerado</div>
          <div className="empty-state-text">Processe um video para comecar</div>
        </div>
      </div>
    )
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-header-left">
          <Scissors className="panel-icon" />
          <span className="panel-title">Cortes Gerados</span>
        </div>
        <span className="panel-badge">{cuts.length} cortes</span>
      </div>

      <div className="panel-body">
        <div className="cuts-list">
          {cuts.map((cut, i) => {
            const isPlaying = playingId === cut.arquivo
            return (
              <div key={i} className="cut-row fade-in" style={{ animationDelay: `${i * 30}ms` }}>
                <div className="cut-row-left">
                  <div className="cut-row-score">
                    {cut.score || '?'}
                  </div>
                  <div className="cut-row-info">
                    <div className="cut-row-title">{cut.titulo}</div>
                    <div className="cut-row-meta">
                      {cut.duracao && (
                        <span>
                          <Clock size={11} />
                          {Math.round(cut.duracao)}s
                        </span>
                      )}
                      {cut.tamanho_mb && (
                        <span>
                          <HardDrive size={11} />
                          {cut.tamanho_mb} MB
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="cut-row-actions">
                  <button
                    className="btn-icon cut-row-btn"
                    onClick={() => handlePlay(cut)}
                    title={isPlaying ? 'Parar' : 'Preview'}
                  >
                    {isPlaying ? <Square size={14} /> : <Play size={14} />}
                  </button>
                  <button
                    className="btn-icon cut-row-btn"
                    onClick={() => onEdit(cut)}
                    title="Editar legenda"
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    className="btn-icon cut-row-btn"
                    onClick={() => handleDownload(cut)}
                    title="Download"
                  >
                    <Download size={14} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>

        {playingId && (
          <div className="cuts-player">
            <video
              src={getStreamUrl(playingId)}
              controls
              autoPlay
              onEnded={() => setPlayingId(null)}
            />
          </div>
        )}
      </div>
    </div>
  )
}
