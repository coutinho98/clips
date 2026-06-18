import { useState, useEffect, useRef, useMemo } from 'react'
import {
  Search, Film, Scissors, MonitorPlay, PanelLeft, Keyboard,
  RotateCcw, Download,
} from 'lucide-react'

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
          id: `cut-${c.arquivo}`,
          group: 'Cortes',
          label: c.titulo || c.arquivo,
          icon: Film,
          hint: c.duracao ? `${Math.round(c.duracao)}s` : '',
          action: () => onEditCut(c),
        }))
      : []

    return [...nav, ...cutResults]
  }, [query, cuts, onNavigate, onEditCut, onToggleSidebar, onShowShortcuts])

  const filtered = query
    ? commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()))
    : commands

  useEffect(() => { setSelectedIdx(0) }, [query])

  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIdx(i => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIdx(i => Math.max(i - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        filtered[selectedIdx]?.action()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [filtered, selectedIdx])

  useEffect(() => {
    const el = resultsRef.current?.querySelector(`[data-idx="${selectedIdx}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [selectedIdx])

  const groups = {}
  filtered.forEach(c => {
    if (!groups[c.group]) groups[c.group] = []
    groups[c.group].push(c)
  })
  const groupNames = Object.keys(groups)
  let runningIdx = 0

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="cmd-palette" onClick={(e) => e.stopPropagation()}>
        <div className="cmd-input-wrap">
          <Search size={16} className="cmd-input-icon" />
          <input
            ref={inputRef}
            className="cmd-input"
            type="text"
            placeholder="Buscar acoes, cortes..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="cmd-results" ref={resultsRef}>
          {filtered.length === 0 ? (
            <div className="cmd-empty">Nenhum resultado para "{query}"</div>
          ) : (
            groupNames.map(gName => (
              <div key={gName}>
                <div className="cmd-group-label">{gName}</div>
                {groups[gName].map(c => {
                  const idx = runningIdx++
                  return (
                    <div
                      key={c.id}
                      data-idx={idx}
                      className={`cmd-item ${idx === selectedIdx ? 'selected' : ''}`}
                      onClick={c.action}
                      onMouseEnter={() => setSelectedIdx(idx)}
                    >
                      <c.icon size={16} className="cmd-item-icon" />
                      <span className="cmd-item-label">{c.label}</span>
                      {c.hint && <span className="cmd-item-hint">{c.hint}</span>}
                    </div>
                  )
                })}
              </div>
            ))
          )}
        </div>

        <div className="cmd-footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> navegar</span>
          <span><kbd>Enter</kbd> selecionar</span>
          <span><kbd>Esc</kbd> fechar</span>
        </div>
      </div>
    </div>
  )
}
