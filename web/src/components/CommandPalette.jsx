import { useState, useEffect, useRef, useMemo } from 'react'
import { Search, Film, Scissors, MonitorPlay, PanelLeft, Keyboard } from 'lucide-react'

export default function CommandPalette({ cuts, onNavigate, onEditCut, onToggleSidebar, onShowShortcuts, onClose }) {
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const inputRef = useRef(null)
  const resultsRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const commands = useMemo(() => {
    const nav = [
      { id: 'nav-import', group: 'Navegar', label: 'Ir para Importar', icon: Film, hint: '1', action: () => onNavigate('import') },
      { id: 'nav-cuts', group: 'Navegar', label: 'Ir para Cortes', icon: Scissors, hint: '2', action: () => onNavigate('cuts') },
      { id: 'nav-editor', group: 'Navegar', label: 'Ir para Editor', icon: MonitorPlay, hint: '3', action: () => onNavigate('editor') },
      { id: 'act-sidebar', group: 'Acoes', label: 'Toggle Sidebar', icon: PanelLeft, hint: 'B', action: onToggleSidebar },
      { id: 'act-shortcuts', group: 'Acoes', label: 'Ver Atalhos', icon: Keyboard, hint: 'Ctrl /', action: onShowShortcuts },
    ]
    const cutResults = query
      ? cuts.filter(c => (c.titulo || '').toLowerCase().includes(query.toLowerCase())).slice(0, 6).map(c => ({
          id: `cut-${c.arquivo}`, group: 'Cortes', label: c.titulo || c.arquivo, icon: Film,
          hint: c.duracao ? `${Math.round(c.duracao)}s` : '', action: () => onEditCut(c),
        })) : []
    return [...nav, ...cutResults]
  }, [query, cuts, onNavigate, onEditCut, onToggleSidebar, onShowShortcuts])

  const filtered = query ? commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase())) : commands
  useEffect(() => { setSelectedIdx(0) }, [query])
  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIdx(i => Math.min(i + 1, filtered.length - 1)) }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIdx(i => Math.max(i - 1, 0)) }
      else if (e.key === 'Enter') { e.preventDefault(); filtered[selectedIdx]?.action() }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [filtered, selectedIdx])
  useEffect(() => { resultsRef.current?.querySelector(`[data-idx="${selectedIdx}"]`)?.scrollIntoView({ block: 'nearest' }) }, [selectedIdx])

  const groups = {}
  filtered.forEach(c => { if (!groups[c.group]) groups[c.group] = []; groups[c.group].push(c) })
  const groupNames = Object.keys(groups)
  let runningIdx = 0

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[1000] flex items-start justify-center pt-[12vh]" style={{ animation: 'modal-fade 150ms ease' }} onClick={onClose}>
      <div className="bg-bg-secondary border border-border-light rounded-xl shadow-2xl w-[90%] max-w-[600px] max-h-[70vh] overflow-hidden flex flex-col" style={{ animation: 'modal-slide 200ms ease' }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <Search size={16} className="text-text-muted shrink-0" />
          <input ref={inputRef} type="text" placeholder="Buscar acoes, cortes..." value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent border-none outline-none text-sm text-text placeholder:text-text-muted" />
        </div>
        <div className="overflow-y-auto p-1.5" ref={resultsRef}>
          {filtered.length === 0 ? (
            <div className="py-6 text-center text-xs text-text-muted">Nenhum resultado para "{query}"</div>
          ) : groupNames.map(gName => (
            <div key={gName}>
              <div className="text-[10px] font-bold uppercase tracking-wide text-text-muted px-2.5 py-2 pt-2">{gName}</div>
              {groups[gName].map(c => {
                const idx = runningIdx++
                return (
                  <div key={c.id} data-idx={idx} onClick={c.action} onMouseEnter={() => setSelectedIdx(idx)}
                    className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md cursor-pointer text-xs transition-colors ${idx === selectedIdx ? 'bg-bg-hover text-text' : 'text-text-secondary'}`}>
                    <c.icon size={16} className={`shrink-0 ${idx === selectedIdx ? 'text-accent-light' : 'text-text-muted'}`} />
                    <span className="flex-1">{c.label}</span>
                    {c.hint && <span className="text-[10px] text-text-muted bg-bg-elevated px-1.5 py-0.5 rounded">{c.hint}</span>}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
        <div className="flex items-center gap-3 px-4 py-2 border-t border-border text-[10px] text-text-muted">
          <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 bg-bg-elevated border border-border rounded text-[9px]">↑↓</kbd> navegar</span>
          <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 bg-bg-elevated border border-border rounded text-[9px]">Enter</kbd> selecionar</span>
          <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 bg-bg-elevated border border-border rounded text-[9px]">Esc</kbd> fechar</span>
        </div>
      </div>
    </div>
  )
}
