import { useState, useEffect, useRef } from 'react'

const REFERENCE_H = 1920

const FONT_CSS = {
  'fira-sans':      { css: "'Fira Sans', sans-serif",            weight: 600 },
  'fira-condensed': { css: "'Fira Sans Condensed', sans-serif",  weight: 700 },
  'open-sans':      { css: "'Open Sans', sans-serif",            weight: 700 },
  'montserrat':     { css: "'Montserrat', sans-serif",           weight: 800 },
  'poppins':        { css: "'Poppins', sans-serif",              weight: 700 },
  'rubik':          { css: "'Rubik', sans-serif",                weight: 700 },
  'raleway':        { css: "'Raleway', sans-serif",              weight: 700 },
  'oswald':         { css: "'Oswald', sans-serif",               weight: 700 },
  'teko':           { css: "'Teko', sans-serif",                 weight: 700 },
  'anton':          { css: "'Anton', sans-serif",                weight: 400 },
  'bebas-neue':     { css: "'Bebas Neue', sans-serif",           weight: 400 },
  'league-spartan': { css: "'League Spartan', sans-serif",       weight: 700 },
  'roboto-slab':    { css: "'Roboto Slab', serif",               weight: 700 },
}

const _S = '0 0 0.08em #000, 0 0.04em 0.1em #000, 0.04em 0.04em 0.06em #000'

const SIMPLE_STYLES = new Set(['neon', 'box', 'sombra'])

const STYLE_ANIMATIONS = {
  karaoke: {
    active: { color: 'var(--sub-highlight, #FFFF32)', textShadow: _S, transition: 'color 0.1s' },
    base:   { color: 'var(--sub-base, #B4B4B4)',      textShadow: _S },
  },
  pop: {
    active: { color: 'var(--sub-highlight, #FFFF32)', textShadow: _S, transform: 'scale(1.3)', transition: 'transform 0.12s cubic-bezier(0.34, 1.56, 0.64, 1)' },
    base:   { color: 'var(--sub-base, #B4B4B4)',      textShadow: _S, transform: 'scale(1)',   transition: 'transform 0.2s' },
  },
  slide: {
    active: { color: 'var(--sub-highlight, #FFFF32)', textShadow: _S, transform: 'translateY(0)',    opacity: 1,   transition: 'all 0.15s ease-out' },
    base:   { color: '#666',                           textShadow: _S, transform: 'translateY(0.7em)', opacity: 0.5, transition: 'all 0.2s' },
  },
  typewriter: {
    active: { color: 'var(--sub-highlight, #FFFF32)', textShadow: _S, opacity: 1,    transition: 'opacity 0.05s' },
    base:   { color: '#333',                          textShadow: _S, opacity: 0.3 },
  },
  rainbow: {
    active: {},
    base:   { color: '#555', textShadow: _S },
  },
  neon: {
    all: { color: '#00ffff', textShadow: '0 0 0.06em #000, 0 0 0.12em #000, 0 0 0.2em #00ffff, 0 0 0.4em #00ffff, 0 0 0.77em #00ffff' },
  },
  box: {
    all: { color: '#ffffff', textShadow: 'none', background: '#000', padding: '0.08em 0.25em', WebkitBoxDecorationBreak: 'clone', boxDecorationBreak: 'clone' },
  },
  sombra: {
    all: { color: 'var(--sub-base, #B4B4B4)', textShadow: '0.08em 0.08em 0.15em #000, 0.06em 0.06em 0.1em #000, 0 0 0.08em #000' },
  },
}

function lerpColor(t) {
  const r = Math.round(255 * (1 - t) + 124 * t)
  const g = Math.round(50 * (1 - t) + 58 * t)
  const b = Math.round(50 * (1 - t) + 237 * t)
  return `rgb(${r},${g},${b})`
}

export default function LiveSubtitle({ videoRef, segmentos, inicioGlobal, style, fontFamily, fontSize, marginBottom, highlightColor, baseColor, onDrag, onResize, dragMode }) {
  const [currentTime, setCurrentTime] = useState(0)
  const [containerH, setContainerH] = useState(0)
  const [dragPosY, setDragPosY] = useState(null)
  const rafRef = useRef(null)
  const wrapperRef = useRef(null)

  useEffect(() => {
    const el = wrapperRef.current?.parentElement
    if (!el) return
    const update = () => setContainerH(el.offsetHeight)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    let lastSegId = null, lastWordIdx = -1
    function tick() {
      const v = videoRef.current
      if (v) {
        const absTime = v.currentTime + (inicioGlobal || 0)
        let newSeg = null, newWordIdx = -1
        if (segmentos?.length > 0) {
          for (const seg of segmentos) {
            if (absTime >= seg.inicio && absTime <= seg.fim) {
              newSeg = seg
              for (let i = 0; i < (seg.words || []).length; i++) {
                const w = seg.words[i]
                const wS = w.inicio || w.start || 0, wE = w.fim || w.end || 0
                if (absTime >= wS && absTime <= wE) { newWordIdx = i; break }
              }
              break
            }
          }
        }
        const newSegId = newSeg?.inicio ?? null
        if (newSegId !== lastSegId || newWordIdx !== lastWordIdx) {
          lastSegId = newSegId; lastWordIdx = newWordIdx
          setCurrentTime(v.currentTime)
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [videoRef, segmentos, inicioGlobal])

  const scaleFactor = containerH > 0 ? containerH / REFERENCE_H : 0
  const scaledFontSize = fontSize * scaleFactor
  const scaledMargin = (dragPosY !== null ? dragPosY : marginBottom * scaleFactor)

  const absTime = currentTime + (inicioGlobal || 0)
  let activeGroup = null, activeWordIdx = -1
  if (segmentos?.length > 0) {
    for (const seg of segmentos) {
      if (absTime >= seg.inicio && absTime <= seg.fim) {
        activeGroup = seg
        for (let i = 0; i < (seg.words || []).length; i++) {
          const w = seg.words[i]
          const wS = w.inicio || w.start || 0, wE = w.fim || w.end || 0
          if (absTime >= wS && absTime <= wE) { activeWordIdx = i; break }
        }
        break
      }
    }
  }

  const anim = STYLE_ANIMATIONS[style] || STYLE_ANIMATIONS.karaoke

  function handleMouseDown(e) {
    if (!dragMode || scaleFactor === 0) return
    e.preventDefault(); e.stopPropagation()
    const startY = e.clientY
    const startPos = scaledMargin
    function onMove(ev) {
      const delta = startY - ev.clientY
      const maxPos = containerH - 30
      const newBottom = Math.max(10, Math.min(maxPos, startPos + delta))
      setDragPosY(newBottom)
      if (onDrag) onDrag(Math.round(newBottom / scaleFactor))
    }
    function onUp() { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
    window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
  }

  function handleResize(e) {
    if (scaleFactor === 0) return
    e.preventDefault(); e.stopPropagation()
    const startX = e.clientX, startY = e.clientY, startFs = fontSize
    function onMove(ev) {
      const delta = (ev.clientX - startX) + (ev.clientY - startY)
      const newFs = Math.max(16, Math.min(120, startFs + delta * 0.5 / scaleFactor))
      if (onResize) onResize(Math.round(newFs))
    }
    function onUp() { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
    window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
  }

  useEffect(() => { if (!dragMode) setDragPosY(null) }, [dragMode])

  const fontInfo = FONT_CSS[fontFamily] || FONT_CSS['fira-sans']

  if (scaleFactor === 0) return <div ref={wrapperRef} className="absolute inset-0 pointer-events-none z-20" />

  const texto = activeGroup?.texto || activeGroup?.text || ''
  const words = texto.split(' ')

  return (
    <div ref={wrapperRef} className="absolute inset-0 pointer-events-none z-20">
      {activeGroup && (
        <div className="absolute left-0 right-0 text-center z-10 select-none px-2 py-1"
          style={{
            bottom: `${scaledMargin}px`,
            fontSize: `${scaledFontSize}px`,
            fontFamily: fontInfo.css,
            fontWeight: fontInfo.weight,
            lineHeight: 1.3,
            cursor: dragMode ? 'move' : 'default',
            pointerEvents: dragMode ? 'auto' : 'none',
            '--sub-highlight': highlightColor,
            '--sub-base': baseColor,
          }}
          onMouseDown={handleMouseDown}>
          <span style={{ display: 'inline' }}>
            {SIMPLE_STYLES.has(style) ? (
              <span style={anim.all}>{texto}</span>
            ) : (
              words.map((word, i) => {
                const isActive = i === activeWordIdx
                const isPast = activeWordIdx >= 0 && i < activeWordIdx
                let styleObj
                if (style === 'rainbow' && isActive) { const t = (Date.now() / 500) % 1; styleObj = { color: lerpColor(t), transition: 'color 0.1s', textShadow: '0 0 0.12em currentColor, ' + _S } }
                else if (style === 'rainbow' && isPast) { styleObj = { color: lerpColor(((i / words.length) + Date.now() / 2000) % 1), textShadow: _S } }
                else if (isActive) { styleObj = anim.active }
                else if (isPast) { styleObj = style === 'slide' ? { ...anim.active, opacity: 0.7 } : anim.active }
                else { styleObj = anim.base }
                return <span key={i} style={styleObj}>{word}{i < words.length - 1 ? '\u00A0' : ''}</span>
              })
            )}
          </span>
          {dragMode && (
            <>
              <div className="absolute -top-4 left-1/2 -translate-x-1/2 text-[9px] text-accent-light bg-accent/10 px-1.5 py-0.5 rounded whitespace-nowrap pointer-events-none">arraste</div>
              <div className="absolute -bottom-1.5 -right-1.5 w-3 h-3 bg-accent border-2 border-white rounded-full cursor-nwse-resize shadow-md pointer-events-auto" onMouseDown={handleResize} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
