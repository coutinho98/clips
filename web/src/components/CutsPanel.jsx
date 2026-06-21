import { useState, useEffect, useCallback } from 'react'
import {
  Play, Square, Pencil, Download, Scissors,
  Clock, HardDrive, Film, Search, ArrowUpDown,
  Copy, FolderOpen, LayoutGrid, List, Tag,
} from 'lucide-react'

const TAG_DEFS = [
  { value: 'engraçado',     emoji: '😂', color: 'yellow' },
  { value: 'drama',          emoji: '🎭', color: 'red' },
  { value: 'reflexão',       emoji: '💭', color: 'blue' },
  { value: 'dica',           emoji: '💡', color: 'green' },
  { value: 'polêmica',       emoji: '🔥', color: 'orange' },
  { value: 'storytelling',   emoji: '📖', color: 'purple' },
  { value: 'emocional',      emoji: '❤️', color: 'pink' },
  { value: 'viral',          emoji: '🚀', color: 'cyan' },
]

const TAG_STYLES = {
  yellow:  { pill: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',   dot: 'bg-yellow-400' },
  red:     { pill: 'bg-red-500/15 text-red-400 border-red-500/30',            dot: 'bg-red-400' },
  blue:    { pill: 'bg-blue-500/15 text-blue-400 border-blue-500/30',         dot: 'bg-blue-400' },
  green:   { pill: 'bg-green-500/15 text-green-400 border-green-500/30',      dot: 'bg-green-400' },
  orange:  { pill: 'bg-orange-500/15 text-orange-400 border-orange-500/30',   dot: 'bg-orange-400' },
  purple:  { pill: 'bg-purple-500/15 text-purple-400 border-purple-500/30',   dot: 'bg-purple-400' },
  pink:    { pill: 'bg-pink-500/15 text-pink-400 border-pink-500/30',         dot: 'bg-pink-400' },
  cyan:    { pill: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',         dot: 'bg-cyan-400' },
}

function tagDef(value) { return TAG_DEFS.find(t => t.value === value) || { emoji: '🏷️', color: 'gray' } }
function tagStyle(value) { return TAG_STYLES[tagDef(value).color] || { pill: 'bg-bg-hover text-text-muted border-border', dot: 'bg-text-muted' } }

function CutThumbnail({ src }) {
  const [failed, setFailed] = useState(false)
  return (
    <div className="w-11 h-7 rounded bg-bg overflow-hidden shrink-0 flex items-center justify-center border border-border">
      {!failed ? (
        <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} className="w-full h-full object-cover" />
      ) : (
        <Film size={16} className="text-text-muted" />
      )}
    </div>
  )
}

function TagPill({ tag, active, onClick, size = 'sm' }) {
  const def = tagDef(tag)
  const st = tagStyle(tag)
  const sz = size === 'xs' ? 'text-[8px] px-1 py-0.5 gap-0.5' : 'text-[9px] px-1.5 py-0.5 gap-1'
  return (
    <button
      className={`inline-flex items-center rounded border transition-all ${sz} ${active ? st.pill : 'bg-bg-elevated text-text-muted border-border hover:text-text opacity-50 hover:opacity-100'}`}
      onClick={(e) => { e.stopPropagation(); onClick?.(tag) }}
    >
      <span>{def.emoji}</span>
      <span className="font-medium">{tag}</span>
    </button>
  )
}

function TagPicker({ cut, onToggleTag, onClose }) {
  return (
    <div className="absolute z-50 top-full right-0 mt-1 bg-bg-secondary border border-border-light rounded-lg shadow-2xl p-2 flex flex-col gap-1 min-w-[140px]" onClick={(e) => e.stopPropagation()}>
      <div className="text-[9px] font-bold uppercase tracking-wide text-text-muted px-1 pb-1">Tags</div>
      {TAG_DEFS.map(t => {
        const active = (cut.tags || []).includes(t.value)
        return (
          <button
            key={t.value}
            className={`flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-medium transition-all border ${active ? tagStyle(t.value).pill : 'text-text-secondary hover:text-text hover:bg-bg-hover border-transparent'}`}
            onClick={(e) => { e.stopPropagation(); onToggleTag(cut, t.value) }}
          >
            <span>{t.emoji}</span>
            <span className="flex-1 text-left">{t.value}</span>
            {active && <span className="text-[8px]">✓</span>}
          </button>
        )
      })}
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
    if (!groups[key]) { groups[key] = []; order.push(key) }
    groups[key].push(cut)
  }
  return { groups, order }
}

function CutRow({ cut, isPlaying, isSelected, onPlay, onEdit, onDownload, onToggle, onContextMenu, onToggleTag }) {
  const [showTags, setShowTags] = useState(false)
  return (
    <div
      className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer transition-all border ${isPlaying ? 'border-success bg-success/10 shadow-[0_0_8px_rgba(16,185,129,0.15)]' : isSelected ? 'border-accent bg-accent/10' : 'bg-bg-elevated border-border hover:border-border-light hover:bg-bg-hover'}`}
      style={{ animation: 'fade-in 0.2s ease forwards' }}
      onContextMenu={onContextMenu}
    >
      <input type="checkbox" className="w-3 h-3 accent-accent cursor-pointer shrink-0" checked={isSelected} onChange={onToggle} />
      <CutThumbnail src={`/api/cuts/${cut.arquivo}/thumb`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-text truncate">{cut.titulo}</span>
          {(cut.tags || []).map(t => (
            <span key={t} className={`inline-flex items-center gap-0.5 text-[8px] px-1 py-0.5 rounded border font-medium shrink-0 ${tagStyle(t).pill}`}>
              {tagDef(t).emoji} {t}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2.5 mt-0.5">
          {cut.duracao && <span className="flex items-center gap-1 text-[10px] text-text-muted"><Clock size={9} /> {Math.round(cut.duracao)}s</span>}
          {cut.tamanho_mb && <span className="flex items-center gap-1 text-[10px] text-text-muted"><HardDrive size={9} /> {cut.tamanho_mb} MB</span>}
        </div>
      </div>
      {cut._new && <span className="text-[9px] font-bold text-success bg-success/15 px-1.5 py-0.5 rounded shrink-0 border border-success/30">NOVO</span>}
      <div className="flex items-center gap-0.5 shrink-0 relative">
        <button className={`flex items-center justify-center w-7 h-7 rounded-md transition-all ${showTags ? 'text-accent-light bg-accent/10' : 'text-text-secondary hover:text-text hover:bg-bg-hover'}`} onClick={(e) => { e.stopPropagation(); setShowTags(v => !v) }} title="Tags">
          <Tag size={13} />
        </button>
        {showTags && <TagPicker cut={cut} onToggleTag={onToggleTag} onClose={() => setShowTags(false)} />}
        <button className="flex items-center justify-center w-7 h-7 rounded-md text-text-secondary hover:text-text hover:bg-bg-hover transition-all" onClick={onPlay} title={isPlaying ? 'Parar' : 'Preview'}>
          {isPlaying ? <Square size={13} /> : <Play size={13} />}
        </button>
        <button className="flex items-center justify-center w-7 h-7 rounded-md text-text-secondary hover:text-text hover:bg-bg-hover transition-all" onClick={onEdit} title="Editar"><Pencil size={13} /></button>
        <button className="flex items-center justify-center w-7 h-7 rounded-md text-text-secondary hover:text-text hover:bg-bg-hover transition-all" onClick={onDownload} title="Download"><Download size={13} /></button>
      </div>
    </div>
  )
}

function CutCard({ cut, isPlaying, isSelected, onPlay, onEdit, onDownload, onToggle, onContextMenu, onToggleTag }) {
  const [showTags, setShowTags] = useState(false)
  return (
    <div
      className={`rounded-lg overflow-hidden cursor-pointer transition-all border ${isPlaying ? 'border-success shadow-[0_0_8px_rgba(16,185,129,0.15)]' : isSelected ? 'border-accent' : 'bg-bg-elevated border-border hover:border-border-light'}`}
      style={{ animation: 'fade-in 0.2s ease forwards' }}
      onContextMenu={onContextMenu}
    >
      <div className="relative aspect-video bg-bg overflow-hidden group" onClick={onPlay}>
        <CutThumbnail src={`/api/cuts/${cut.arquivo}/thumb`} />
        <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="w-10 h-10 rounded-full bg-accent/80 flex items-center justify-center">
            {isPlaying ? <Square size={18} className="text-white" /> : <Play size={18} className="text-white" />}
          </div>
        </div>
        {cut.duracao && (
          <span className="absolute bottom-1.5 right-1.5 text-[9px] text-white bg-black/70 px-1.5 py-0.5 rounded">{Math.round(cut.duracao)}s</span>
        )}
        {cut._new && <span className="absolute top-1.5 left-1.5 text-[9px] font-bold text-success bg-success/20 px-1.5 py-0.5 rounded border border-success/40">NOVO</span>}
      </div>
      <div className="p-2">
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-xs font-medium text-text truncate flex-1" title={cut.titulo}>{cut.titulo}</span>
          <input type="checkbox" className="w-3 h-3 accent-accent cursor-pointer shrink-0" checked={isSelected} onChange={onToggle} />
          <div className="relative">
            <button className={`flex items-center justify-center w-6 h-6 rounded-md transition-all ${showTags ? 'text-accent-light bg-accent/10' : 'text-text-secondary hover:text-text hover:bg-bg-hover'}`} onClick={(e) => { e.stopPropagation(); setShowTags(v => !v) }} title="Tags">
              <Tag size={12} />
            </button>
            {showTags && <TagPicker cut={cut} onToggleTag={onToggleTag} onClose={() => setShowTags(false)} />}
          </div>
          <button className="flex items-center justify-center w-6 h-6 rounded-md text-text-secondary hover:text-text hover:bg-bg-hover transition-all" onClick={onEdit} title="Editar"><Pencil size={12} /></button>
          <button className="flex items-center justify-center w-6 h-6 rounded-md text-text-secondary hover:text-text hover:bg-bg-hover transition-all" onClick={onDownload} title="Download"><Download size={12} /></button>
        </div>
        {(cut.tags || []).length > 0 && (
          <div className="flex flex-wrap gap-1">
            {cut.tags.map(t => (
              <span key={t} className={`inline-flex items-center gap-0.5 text-[8px] px-1 py-0.5 rounded border font-medium ${tagStyle(t).pill}`}>
                {tagDef(t).emoji} {t}
              </span>
            ))}
          </div>
        )}
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
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('dcb-view') || 'list')
  const [activeTags, setActiveTags] = useState(new Set())
  const [localCuts, setLocalCuts] = useState(cuts)

  useEffect(() => { setLocalCuts(cuts) }, [cuts])

  useEffect(() => {
    function handleClick() { setContextMenu(null) }
    window.addEventListener('click', handleClick)
    return () => window.removeEventListener('click', handleClick)
  }, [])

  const handleToggleTag = useCallback(async (cut, tag) => {
    const current = cut.tags || []
    const newTags = current.includes(tag) ? current.filter(t => t !== tag) : [...current, tag]

    setLocalCuts(prev => prev.map(c => c.arquivo === cut.arquivo ? { ...c, tags: newTags } : c))

    try {
      await fetch(`/api/cut/${encodeURIComponent(cut.cut_id)}/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags: newTags }),
      })
    } catch (e) { console.error('Failed to save tags:', e) }
  }, [])

  function handlePlay(cut) { setPlayingId(playingId === cut.arquivo ? null : cut.arquivo) }
  function handleDownload(cut) {
    const a = document.createElement('a')
    a.href = `/api/cuts/${cut.arquivo}/download`
    a.download = cut.arquivo
    a.click()
  }
  function handleCopyTitle(cut) { navigator.clipboard?.writeText(cut.titulo || '') }

  function toggleSelect(id) {
    setSelectedIds(prev => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next })
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
  function toggleFilterTag(tag) {
    setActiveTags(prev => { const next = new Set(prev); if (next.has(tag)) next.delete(tag); else next.add(tag); return next })
  }

  const { groups, order } = groupByFolder(localCuts || [])
  const filteredFolders = folderSearch
    ? order.filter(k => prettyFolderName(k).toLowerCase().includes(folderSearch.toLowerCase()))
    : order

  let displayCuts = selectedFolder !== null ? (groups[selectedFolder] || []) : localCuts
  if (searchQuery) {
    displayCuts = displayCuts.filter(c => (c.titulo || '').toLowerCase().includes(searchQuery.toLowerCase()))
  }
  if (activeTags.size > 0) {
    displayCuts = displayCuts.filter(c => {
      const cutTags = new Set(c.tags || [])
      for (const t of activeTags) { if (cutTags.has(t)) return true }
      return false
    })
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

  const tagCounts = {}
  for (const c of (localCuts || [])) {
    for (const t of (c.tags || [])) { tagCounts[t] = (tagCounts[t] || 0) + 1 }
  }

  if (!localCuts || localCuts.length === 0) {
    return (
      <div className="bg-bg-tertiary border border-border rounded-xl overflow-hidden flex flex-col h-full">
        <div className="flex items-center px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <Scissors size={14} className="text-accent-light" />
            <span className="text-xs font-semibold text-text">Cortes Gerados</span>
          </div>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-3 py-12">
          <svg width="120" height="90" viewBox="0 0 120 90" fill="none">
            <rect x="15" y="15" width="90" height="56" rx="6" stroke="#3f3f46" strokeWidth="1.5" fill="#1c1c21" />
            <path d="M15 30 L105 30" stroke="#27272a" strokeWidth="1" />
            <circle cx="20" cy="22" r="1.5" fill="#ef4444" />
            <circle cx="25" cy="22" r="1.5" fill="#f59e0b" />
            <circle cx="30" cy="22" r="1.5" fill="#10b981" />
            <path d="M45 45 L45 55 M40 50 L50 50" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" className="animate-pulse" />
            <rect x="60" y="42" width="30" height="3" rx="1.5" fill="#3f3f46" />
            <rect x="60" y="50" width="20" height="3" rx="1.5" fill="#27272a" />
            <path d="M55 71 L55 78 M60 71 L60 78 M65 71 L65 78" stroke="#27272a" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <div className="text-sm font-semibold text-text">Nenhum corte gerado</div>
          <div className="text-xs text-text-muted text-center max-w-xs">Importe e processe um video para gerar cortes automaticamente com IA</div>
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white rounded-md text-xs font-medium hover:bg-accent-hover transition-all" onClick={onGoImport}>
            <Film size={14} /> Importar Video
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full overflow-hidden bg-bg-tertiary">
      {/* Sidebar */}
      <div className="w-52 shrink-0 border-r border-border flex flex-col bg-bg-secondary">
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-border shrink-0">
          <span className="text-[11px] font-bold uppercase tracking-wide text-text-muted">Lives</span>
          <span className="text-[10px] font-bold text-accent-light bg-accent/10 px-1.5 py-0.5 rounded border border-accent/20 min-w-[18px] text-center">{order.length}</span>
        </div>
        <input className="mx-2.5 my-2 px-2.5 py-1.5 bg-bg-elevated border border-border rounded-md text-[11px] text-text outline-none focus:border-accent" type="text" placeholder="Buscar live..."
          value={folderSearch} onChange={(e) => setFolderSearch(e.target.value)} />
        <div className="flex-1 overflow-y-auto px-1.5 pb-2 flex flex-col gap-0.5">
          <div
            className={`flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-[11px] transition-colors border ${selectedFolder === null ? 'bg-accent/15 text-accent-light border-accent/30' : 'text-text-secondary hover:bg-bg-hover hover:text-text border-transparent'}`}
            onClick={() => setSelectedFolder(null)}
          >
            <Film size={13} className="shrink-0" />
            <span className="flex-1 truncate">Todos os cortes</span>
            <span className="text-[10px] text-text-muted">{localCuts.length}</span>
          </div>
          {filteredFolders.map(folderKey => (
            <div
              key={folderKey}
              className={`flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-[11px] transition-colors border ${selectedFolder === folderKey ? 'bg-accent/15 text-accent-light border-accent/30' : 'text-text-secondary hover:bg-bg-hover hover:text-text border-transparent'}`}
              onClick={() => setSelectedFolder(folderKey)}
            >
              <FolderOpen size={13} className="shrink-0" />
              <span className="flex-1 truncate">{prettyFolderName(folderKey)}</span>
              <span className="text-[10px] text-text-muted">{groups[folderKey].length}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center gap-2 px-3.5 pt-2.5 pb-0 shrink-0 flex-wrap">
          <input className="flex-1 min-w-[120px] px-2.5 py-1.5 bg-bg-elevated border border-border rounded-md text-xs text-text outline-none focus:border-accent" type="text" placeholder="Buscar cortes..."
            value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
          {[
            { key: 'score', label: 'Score' },
            { key: 'duracao', label: 'Duracao' },
            { key: 'titulo', label: 'Titulo' },
          ].map(s => (
            <button key={s.key}
              className={`flex items-center gap-1 px-2 py-1.5 rounded-md text-[10px] font-medium transition-all border ${sortBy === s.key ? 'bg-accent text-white border-accent' : 'bg-bg-elevated border-border text-text-secondary hover:text-text hover:border-border-light'}`}
              onClick={() => handleSort(s.key)}
            >
              <ArrowUpDown size={10} /> {s.label}
            </button>
          ))}
          <div className="flex bg-bg-elevated border border-border rounded-md p-0.5">
            <button className={`flex items-center justify-center w-7 h-6 rounded transition-all ${viewMode === 'list' ? 'bg-accent text-white' : 'text-text-secondary hover:text-text'}`}
              onClick={() => { setViewMode('list'); localStorage.setItem('dcb-view', 'list') }} title="Lista">
              <List size={13} />
            </button>
            <button className={`flex items-center justify-center w-7 h-6 rounded transition-all ${viewMode === 'grid' ? 'bg-accent text-white' : 'text-text-secondary hover:text-text'}`}
              onClick={() => { setViewMode('grid'); localStorage.setItem('dcb-view', 'grid') }} title="Grid">
              <LayoutGrid size={13} />
            </button>
          </div>
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 ml-auto text-[11px]">
              <span className="text-text-secondary">{selectedIds.size} selecionado(s)</span>
              <button className="px-2 py-1 bg-accent text-white rounded text-[10px] font-medium hover:bg-accent-hover transition-all" onClick={() => batchDownload(displayCuts)}>Baixar selecionados</button>
              <button className="px-2 py-1 bg-bg-elevated border border-border text-text-secondary rounded text-[10px] font-medium hover:text-text hover:bg-bg-hover transition-all" onClick={() => setSelectedIds(new Set())}>Desselecionar</button>
            </div>
          )}
        </div>

        {/* Tag filter bar */}
        <div className="flex items-center gap-1 px-3.5 py-1.5 shrink-0 flex-wrap">
          <span className="text-[9px] font-bold uppercase tracking-wide text-text-muted mr-1">Filtrar:</span>
          {TAG_DEFS.map(t => {
            const count = tagCounts[t.value] || 0
            const isActive = activeTags.has(t.value)
            return (
              <button
                key={t.value}
                className={`inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded border font-medium transition-all ${isActive ? tagStyle(t.value).pill : 'bg-bg-elevated text-text-muted border-border hover:text-text'}`}
                onClick={() => toggleFilterTag(t.value)}
              >
                <span>{t.emoji}</span>
                <span>{t.value}</span>
                {count > 0 && <span className={`text-[8px] ${isActive ? 'opacity-70' : 'opacity-50'}`}>{count}</span>}
              </button>
            )
          })}
          {activeTags.size > 0 && (
            <button className="text-[9px] text-text-muted hover:text-accent-light ml-1 transition-colors" onClick={() => setActiveTags(new Set())}>
              limpar
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-3.5 pt-1 flex flex-col gap-1">
          {displayCuts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-text-muted">
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none" className="mb-2">
                <circle cx="20" cy="20" r="14" stroke="#3f3f46" strokeWidth="2" />
                <path d="M30 30 L40 40" stroke="#3f3f46" strokeWidth="2" strokeLinecap="round" />
                <path d="M15 20 L25 20 M20 15 L20 25" stroke="#6b6b76" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <span className="text-xs">Nenhum corte encontrado</span>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2.5">
              {displayCuts.map((cut) => (
                <CutCard key={cut.arquivo} cut={cut}
                  isPlaying={playingId === cut.arquivo} isSelected={selectedIds.has(cut.arquivo)}
                  onPlay={() => handlePlay(cut)} onEdit={() => onEdit(cut)} onDownload={() => handleDownload(cut)}
                  onToggle={() => toggleSelect(cut.arquivo)} onContextMenu={(e) => handleContextMenu(e, cut)}
                  onToggleTag={handleToggleTag} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              {displayCuts.map((cut) => (
                <CutRow key={cut.arquivo} cut={cut}
                  isPlaying={playingId === cut.arquivo} isSelected={selectedIds.has(cut.arquivo)}
                  onPlay={() => handlePlay(cut)} onEdit={() => onEdit(cut)} onDownload={() => handleDownload(cut)}
                  onToggle={() => toggleSelect(cut.arquivo)} onContextMenu={(e) => handleContextMenu(e, cut)}
                  onToggleTag={handleToggleTag} />
              ))}
            </div>
          )}

          {playingId && (
            <div className="fixed bottom-12 right-4 z-50 bg-bg-secondary border border-border-light rounded-lg overflow-hidden shadow-2xl" style={{ animation: 'fade-in 0.2s ease forwards' }}>
              <video src={`/api/cuts/${playingId}`} controls autoPlay onEnded={() => setPlayingId(null)} className="w-[270px] max-h-[480px]" />
            </div>
          )}
        </div>
      </div>

      {contextMenu && contextCut && (
        <div className="fixed z-[999] bg-bg-secondary border border-border-light rounded-lg shadow-2xl py-1 min-w-[160px]" style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}>
          {[
            { icon: Play, label: playingId === contextCut.arquivo ? 'Parar' : 'Preview', action: () => { handlePlay(contextCut); setContextMenu(null) } },
            { icon: Pencil, label: 'Editar legenda', action: () => { onEdit(contextCut); setContextMenu(null) } },
            { icon: Download, label: 'Download', action: () => { handleDownload(contextCut); setContextMenu(null) } },
          ].map((item, i) => (
            <div key={i} className="flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-text hover:bg-bg-hover cursor-pointer transition-colors"
              onClick={item.action}>
              <item.icon size={13} /> {item.label}
            </div>
          ))}
          <div className="h-px bg-border my-1" />
          <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-text hover:bg-bg-hover cursor-pointer transition-colors"
            onClick={() => { handleCopyTitle(contextCut); setContextMenu(null) }}>
            <Copy size={13} /> Copiar titulo
          </div>
        </div>
      )}
    </div>
  )
}
