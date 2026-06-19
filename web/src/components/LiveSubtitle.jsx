import { useState, useEffect, useRef } from 'react'

const STYLE_ANIMATIONS = {
  karaoke: { active: { color: 'var(--sub-highlight, #FFFF32)', transition: 'color 0.08s' }, base: { color: 'var(--sub-base, #B4B4B4)' } },
  neon: { active: { color: '#00ffff', textShadow: '0 0 8px #00ffff, 0 0 16px #00ffff', transition: 'all 0.15s' }, base: { color: '#ffffff', textShadow: 'none' } },
  pop: { active: { color: '#FFFF32', transform: 'scale(1.15)', transition: 'transform 0.12s cubic-bezier(0.34, 1.56, 0.64, 1)' }, base: { color: '#B4B4B4', transform: 'scale(1)', transition: 'transform 0.2s' } },
  slide: { active: { color: '#FFFF32', transform: 'translateY(0)', opacity: 1, transition: 'all 0.15s ease-out' }, base: { color: '#888', transform: 'translateY(8px)', opacity: 0.4, transition: 'all 0.2s' } },
  typewriter: { active: { color: '#FFFF32', opacity: 1, transition: 'opacity 0.05s' }, base: { color: '#444', opacity: 0.3 } },
  rainbow: { active: {}, base: { color: '#555' } },
}

function lerpColor(t) {
  const r = Math.round(255 * (1 - t) + 124 * t)
  const g = Math.round(50 * (1 - t) + 58 * t)
  const b = Math.round(50 * (1 - t) + 237 * t)
  return `rgb(${r},${g},${b})`
}

export default function LiveSubtitle({ videoRef, segmentos, inicioGlobal, style, fontSize, marginBottom, highlightColor, baseColor, onDrag, onResize, dragMode }) {
  const [currentTime, setCurrentTime] = useState(0)
  const [posY, setPosY] = useState(marginBottom)
  const [fs, setFs] = useState(fontSize)
  const rafRef = useRef(null)

  useEffect(() => { setPosY(marginBottom) }, [marginBottom])
  useEffect(() => { setFs(fontSize) }, [fontSize])
  useEffect(() => {
    function tick() { const v = videoRef.current; if (v) setCurrentTime(v.currentTime); rafRef.current = requestAnimationFrame(tick) }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [videoRef])

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
    if (!dragMode) return
    e.preventDefault(); e.stopPropagation()
    const startY = e.clientY, startYPos = posY
    const container = e.currentTarget.parentElement.parentElement
    const containerH = container.offsetHeight
    function onMove(ev) {
      const delta = startY - ev.clientY
      const newBottom = Math.max(20, Math.min(containerH - 40, startYPos + delta))
      setPosY(newBottom); if (onDrag) onDrag(newBottom)
    }
    function onUp() { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
    window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
  }

  function handleResize(e) {
    e.preventDefault(); e.stopPropagation()
    const startX = e.clientX, startY = e.clientY, startFs = fs
    function onMove(ev) {
      const delta = (ev.clientX - startX) + (ev.clientY - startY)
      const newFs = Math.max(16, Math.min(120, startFs + delta * 0.5))
      setFs(Math.round(newFs)); if (onResize) onResize(Math.round(newFs))
    }
    function onUp() { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
    window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
  }

  if (!activeGroup) return null
  const texto = activeGroup.texto || activeGroup.text || ''
  const words = texto.split(' ')

  return (
    <div className="absolute left-0 right-0 text-center z-10 select-none px-2 py-1"
      style={{ bottom: `${posY}px`, fontSize: `${fs}px`, fontFamily: 'Fira Sans, sans-serif', fontWeight: 700, lineHeight: 1.3, cursor: dragMode ? 'move' : 'default', '--sub-highlight': highlightColor, '--sub-base': baseColor }}
      onMouseDown={handleMouseDown}>
      <span style={{ display: 'inline', textShadow: '2px 2px 4px rgba(0,0,0,0.9)' }}>
        {words.map((word, i) => {
          const isActive = i === activeWordIdx
          const isPast = activeWordIdx >= 0 && i < activeWordIdx
          let styleObj
          if (style === 'rainbow' && isActive) { const t = (Date.now() / 500) % 1; styleObj = { color: lerpColor(t), transition: 'color 0.1s', textShadow: '0 0 6px currentColor' } }
          else if (style === 'rainbow' && isPast) { styleObj = { color: lerpColor(((i / words.length) + Date.now() / 2000) % 1) } }
          else if (isActive) { styleObj = anim.active }
          else if (isPast) { styleObj = style === 'slide' ? { ...anim.active, opacity: 0.7 } : anim.active }
          else { styleObj = anim.base }
          return <span key={i} style={styleObj}>{word}{i < words.length - 1 ? '\u00A0' : ''}</span>
        })}
      </span>
      {dragMode && (
        <>
          <div className="absolute -top-4 left-1/2 -translate-x-1/2 text-[9px] text-accent-light bg-accent/10 px-1.5 py-0.5 rounded whitespace-nowrap pointer-events-none">arraste</div>
          <div className="absolute -bottom-1.5 -right-1.5 w-3 h-3 bg-accent border-2 border-white rounded-full cursor-nwse-resize shadow-md" onMouseDown={handleResize} />
        </>
      )}
    </div>
  )
}
