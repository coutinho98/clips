import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, Square, Pencil, Download, Scissors,
  Clock, HardDrive, Film, Search, ArrowUpDown,
  Copy, FolderOpen,
} from 'lucide-react'

function CutThumbnail({ src }) {
  const [thumbUrl, setThumbUrl] = useState(null)

  useEffect(() => {
    const video = document.createElement('video')
    video.crossOrigin = 'anonymous'
    video.preload = 'metadata'
    video.muted = true
    video.playsInline = true
    let revoked = false

    video.addEventListener('loadeddata', () => {
      video.currentTime = Math.min(1, (video.duration || 2) * 0.1)
    })

    video.addEventListener('seeked', () => {
      if (revoked) return
      try {
        const vw = video.videoWidth || 320
        const vh = video.videoHeight || 180
        const scale = Math.min(320 / vw, 320 / vh)
        const cw = Math.round(vw * scale)
        const ch = Math.round(vh * scale)
        const canvas = document.createElement('canvas')
        canvas.width = cw
        canvas.height = ch
        const ctx = canvas.getContext('2d')
        ctx.drawImage(video, 0, 0, cw, ch)
        setThumbUrl(canvas.toDataURL('image/jpeg', 0.85))
      } catch {}
    })

    video.addEventListener('error', () => {})
    video.src = src
    return () => { revoked = true }
  }, [src])

  return (
    <div className="cut-row-thumb">
      {thumbUrl ? <img src={thumbUrl} alt="" /> : <Film className="cut-row-thumb-placeholder" size={16} />}
    </div>
  )
}

function prettyFolderName(name) {
  if (!name) return 'Sem pasta'
  return name.replace(/_/g, ' ').replace(/-/g, ' - ')
}

function groupByFolder(cuts) {
  const groups = {}
  const order = []
  for (const cut of cuts) {
    const key = cut.pasta || ''
    if (!groups[key]) {
      groups[key] = []
      order.push(key)
    }
    groups[key].push(cut)
  }
  return { groups, order }
}

function CutRow({ cut, isPlaying, isSelected, onPlay, onEdit, onDownload, onToggle, onContextMenu }) {
  return (
    <div
      className={`cut-row fade-in ${isPlaying ? 'playing' : ''} ${isSelected ? 'selected' : ''}`}
      onContextMenu={onContextMenu}
    >
      <input type="checkbox" className="cut-row-checkbox" checked={isSelected} onChange={onToggle} />
      <CutThumbnail src={`/api/cuts/${cut.arquivo}`} />
      <div className="cut-row-left">
        <div className="cut-row-info">
          <div className="cut-row-title">{cut.titulo}</div>
          <div className="cut-row-meta">
            {cut.duracao && <span><Clock size={10} /> {Math.round(cut.duracao)}s</span>}
            {cut.tamanho_mb && <span><HardDrive size={10} /> {cut.tamanho_mb} MB</span>}
          </div>
        </div>
      </div>
      {cut._new && <span className="new-badge">NOVO</span>}
      <div className="cut-row-actions">
        <button className="btn-icon cut-row-btn" onClick={onPlay} title={isPlaying ? 'Parar' : 'Preview'}>
          {isPlaying ? <Square size={13} /> : <Play size={13} />}
        </button>
        <button className="btn-icon cut-row-btn" onClick={onEdit} title="Editar"><Pencil size={13} /></button>
        <button className="btn-icon cut-row-btn" onClick={onDownload} title="Download"><Download size={13} /></button>
      </div>
    </div>
  )
}

export default function CutsPanel({ cuts, onEdit, onGoImport }) {
  const [playingId, setPlayingId] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState('none')
  const [sortDir, setSortDir] = useState('desc')
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [contextMenu, setContextMenu] = useState(null)
  const [contextCut, setContextCut] = useState(null)
  const [selectedFolder, setSelectedFolder] = useState(null)
  const [folderSearch, setFolderSearch] = useState('')

  useEffect(() => {
    function handleClick() { setContextMenu(null) }
    window.addEventListener('click', handleClick)
    return () => window.removeEventListener('click', handleClick)
  }, [])

  function handlePlay(cut) {
    setPlayingId(playingId === cut.arquivo ? null : cut.arquivo)
  }

  function handleDownload(cut) {
    const a = document.createElement('a')
    a.href = `/api/cuts/${cut.arquivo}/download`
    a.download = cut.arquivo
    a.click()
  }

  function handleCopyTitle(cut) {
    navigator.clipboard?.writeText(cut.titulo || '')
  }

  function toggleSelect(id) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleSelectAll(cutList) {
    const allSelected = cutList.every(c => selectedIds.has(c.arquivo))
    setSelectedIds(prev => {
      const next = new Set(prev)
      cutList.forEach(c => { allSelected ? next.delete(c.arquivo) : next.add(c.arquivo) })
      return next
    })
  }

  function batchDownload(cutList) {
    cutList.filter(c => selectedIds.has(c.arquivo)).forEach(c => handleDownload(c))
  }

  function handleSort(field) {
    if (sortBy === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortBy(field); setSortDir('desc') }
  }

  function handleContextMenu(e, cut) {
    e.preventDefault()
    setContextMenu({ x: e.clientX, y: e.clientY })
    setContextCut(cut)
  }

  const { groups, order } = groupByFolder(cuts || [])
  const hasFolders = order.length > 1 || (order.length === 1 && order[0] !== '')

  const filteredFolders = folderSearch
    ? order.filter(k => prettyFolderName(k).toLowerCase().includes(folderSearch.toLowerCase()))
    : order

  let displayCuts = selectedFolder !== null
    ? (groups[selectedFolder] || [])
    : cuts

  if (searchQuery) {
    displayCuts = displayCuts.filter(c =>
      (c.titulo || '').toLowerCase().includes(searchQuery.toLowerCase())
    )
  }

  if (sortBy !== 'none') {
    displayCuts = [...displayCuts].sort((a, b) => {
      let va, vb
      if (sortBy === 'score') { va = parseFloat(a.score) || 0; vb = parseFloat(b.score) || 0 }
      else if (sortBy === 'duracao') { va = a.duracao || 0; vb = b.duracao || 0 }
      else if (sortBy === 'tamanho') { va = a.tamanho_mb || 0; vb = b.tamanho_mb || 0 }
      else { va = (a.titulo || '').toLowerCase(); vb = (b.titulo || '').toLowerCase() }
      const cmp = va < vb ? -1 : va > vb ? 1 : 0
      return sortDir === 'asc' ? cmp : -cmp
    })
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
          <button className="empty-state-action" onClick={onGoImport}>
            <Film size={14} /> Importar Video
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="cuts-browser">
      <div className="cuts-sidebar">
        <div className="cuts-sidebar-header">
          <span className="cuts-sidebar-title">Lives</span>
          <span className="panel-badge">{order.length}</span>
        </div>
        <input className="cuts-folder-search" type="text" placeholder="Buscar live..."
          value={folderSearch} onChange={(e) => setFolderSearch(e.target.value)} />
        <div className="cuts-sidebar-list">
          <div
            className={`cuts-sidebar-item ${selectedFolder === null ? 'active' : ''}`}
            onClick={() => setSelectedFolder(null)}
          >
            <Film size={14} />
            <span className="cuts-sidebar-item-name">Todos os cortes</span>
            <span className="cuts-sidebar-item-count">{cuts.length}</span>
          </div>
          {filteredFolders.map(folderKey => (
            <div
              key={folderKey}
              className={`cuts-sidebar-item ${selectedFolder === folderKey ? 'active' : ''}`}
              onClick={() => setSelectedFolder(folderKey)}
            >
              <FolderOpen size={14} />
              <span className="cuts-sidebar-item-name">{prettyFolderName(folderKey)}</span>
              <span className="cuts-sidebar-item-count">{groups[folderKey].length}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="cuts-main">
        <div className="cuts-main-header">
          <div className="cuts-toolbar">
            <input className="cuts-search" type="text" placeholder="Buscar cortes..."
              value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
            <button className={`cuts-sort-btn ${sortBy === 'score' ? 'active' : ''}`} onClick={() => handleSort('score')}>
              <ArrowUpDown size={10} /> Score
            </button>
            <button className={`cuts-sort-btn ${sortBy === 'duracao' ? 'active' : ''}`} onClick={() => handleSort('duracao')}>
              <ArrowUpDown size={10} /> Duracao
            </button>
            <button className={`cuts-sort-btn ${sortBy === 'titulo' ? 'active' : ''}`} onClick={() => handleSort('titulo')}>
              <ArrowUpDown size={10} /> Titulo
            </button>
          </div>

          {selectedIds.size > 0 && (
            <div className="cuts-batch-actions">
              {selectedIds.size} selecionado(s)
              <button onClick={() => batchDownload(displayCuts)}>Baixar selecionados</button>
              <button onClick={() => setSelectedIds(new Set())}>Desselecionar</button>
            </div>
          )}
        </div>

        <div className="cuts-main-body">
          {displayCuts.length === 0 ? (
            <div className="cuts-main-empty">
              <Film size={28} style={{ opacity: 0.2, marginBottom: 8 }} />
              <span>Nenhum corte encontrado</span>
            </div>
          ) : (
            <div className="cuts-list">
              {displayCuts.map((cut) => (
                <CutRow
                  key={cut.arquivo}
                  cut={cut}
                  isPlaying={playingId === cut.arquivo}
                  isSelected={selectedIds.has(cut.arquivo)}
                  onPlay={() => handlePlay(cut)}
                  onEdit={() => onEdit(cut)}
                  onDownload={() => handleDownload(cut)}
                  onToggle={() => toggleSelect(cut.arquivo)}
                  onContextMenu={(e) => handleContextMenu(e, cut)}
                />
              ))}
            </div>
          )}

          {playingId && (
            <div className="cuts-player fade-in">
              <video src={`/api/cuts/${playingId}`} controls autoPlay onEnded={() => setPlayingId(null)} />
            </div>
          )}
        </div>
      </div>

      {contextMenu && contextCut && (
        <div className="context-menu" style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}>
          <div className="context-menu-item" onClick={() => { handlePlay(contextCut); setContextMenu(null) }}>
            <Play size={13} /> {playingId === contextCut.arquivo ? 'Parar' : 'Preview'}
          </div>
          <div className="context-menu-item" onClick={() => { onEdit(contextCut); setContextMenu(null) }}>
            <Pencil size={13} /> Editar legenda
          </div>
          <div className="context-menu-item" onClick={() => { handleDownload(contextCut); setContextMenu(null) }}>
            <Download size={13} /> Download
          </div>
          <div className="context-menu-divider" />
          <div className="context-menu-item" onClick={() => { handleCopyTitle(contextCut); setContextMenu(null) }}>
            <Copy size={13} /> Copiar titulo
          </div>
        </div>
      )}
    </div>
  )
}
