import { useState, useEffect, useRef } from 'react'

export default function Timeline({ videoRef, duration, segmentos, inicioGlobal, onSeek }) {
  const canvasRef = useRef(null)
  const containerRef = useRef(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [waveform, setWaveform] = useState(null)
  const [loading, setLoading] = useState(true)
  const [thumbnails, setThumbnails] = useState([])
  const rafRef = useRef(null)
  const dragRef = useRef(false)

  useEffect(() => {
    function tick() { const v = videoRef.current; if (v && !v.paused) setCurrentTime(v.currentTime); rafRef.current = requestAnimationFrame(tick) }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [videoRef])

  const videoSrc = videoRef.current?.src

  useEffect(() => {
    if (!videoSrc) return
    let cancelled = false
    async function generateWaveform() {
      try {
        setLoading(true)
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
        const res = await fetch(videoSrc)
        const arrayBuf = await res.arrayBuffer()
        const audioBuf = await audioCtx.decodeAudioData(arrayBuf)
        if (cancelled) return
        const channel = audioBuf.getChannelData(0)
        const samples = 200, blockSize = Math.floor(channel.length / samples), peaks = []
        for (let i = 0; i < samples; i++) { let max = 0; const start = i * blockSize; for (let j = 0; j < blockSize; j++) { const val = Math.abs(channel[start + j] || 0); if (val > max) max = val } peaks.push(max) }
        const maxPeak = Math.max(...peaks, 0.001)
        if (!cancelled) { setWaveform(peaks.map(p => p / maxPeak)); setThumbnails(Array.from({ length: 12 }, (_, i) => ({ time: (i / 12) * audioBuf.duration }))) }
        audioCtx.close()
      } catch { if (!cancelled) setWaveform(null) } finally { if (!cancelled) setLoading(false) }
    }
    generateWaveform()
    return () => { cancelled = true }
  }, [videoSrc])

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas || !waveform) return
    const ctx = canvas.getContext('2d')
    canvas.width = canvas.offsetWidth * 2; canvas.height = canvas.offsetHeight * 2
    ctx.scale(2, 2)
    const cw = canvas.offsetWidth, ch = canvas.offsetHeight
    ctx.clearRect(0, 0, cw, ch)
    const barW = cw / waveform.length, midH = ch / 2
    for (let i = 0; i < waveform.length; i++) {
      const peak = waveform[i], barH = peak * ch * 0.85, x = i * barW
      const progress = duration > 0 ? currentTime / duration : 0
      ctx.fillStyle = (i / waveform.length) < progress ? '#7c3aed' : '#3f3f46'
      ctx.fillRect(x + barW * 0.15, midH - barH / 2, barW * 0.7, barH)
    }
  }, [waveform, currentTime, duration])

  function handleSeek(e) {
    const rect = containerRef.current.getBoundingClientRect()
    const t = ((e.clientX - rect.left) / rect.width) * (duration || 0)
    if (videoRef.current) videoRef.current.currentTime = t
    setCurrentTime(t); if (onSeek) onSeek(t)
  }
  function handleMouseDown(e) {
    dragRef.current = true; handleSeek(e)
    function onMove(ev) { if (dragRef.current) handleSeek(ev) }
    function onUp() { dragRef.current = false; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
    window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
  }

  const playheadPct = duration > 0 ? (currentTime / duration) * 100 : 0
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s) % 60).padStart(2, '0')}`

  return (
    <div className="shrink-0 bg-bg-secondary border-t border-border px-3 py-2 flex flex-col gap-1">
      <div className="relative h-[18px] ml-[60px]">
        {[0, 0.25, 0.5, 0.75, 1].map(pct => (
          <div key={pct} className="absolute top-0" style={{ left: `${pct * 100}%` }}>
            <div className="w-px h-1.5 bg-border-light" />
            <span className="absolute top-[7px] left-0.5 text-[9px] text-text-muted whitespace-nowrap">{pct === 0 ? '0:00' : fmt(pct * duration)}</span>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[9px] font-semibold uppercase tracking-wide text-text-muted w-[52px] shrink-0">Video</span>
        <div className="flex gap-px flex-1 h-7 bg-bg rounded overflow-hidden border border-border">
          {thumbnails.map((t, i) => (
            <div key={i} className="flex-1 h-full overflow-hidden bg-bg-tertiary border-r border-border last:border-r-0">
              <video src={videoSrc} preload="metadata" muted
                style={{ width: '100%', height: '100%', objectFit: 'cover', pointerEvents: 'none' }}
                ref={(el) => { if (el) el.currentTime = t.time }} />
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[9px] font-semibold uppercase tracking-wide text-text-muted w-[52px] shrink-0">Audio</span>
        <div ref={containerRef} className="relative flex-1 h-12 bg-bg border border-border rounded overflow-hidden cursor-pointer" onMouseDown={handleMouseDown}>
          {loading ? <div className="flex items-center justify-center h-full text-[10px] text-text-muted">decodificando audio...</div>
            : <canvas ref={canvasRef} className="w-full h-full block" />}
          <div className="absolute top-0 bottom-0 w-0.5 pointer-events-none z-[5]" style={{ left: `${playheadPct}%` }}>
            <div className="w-0.5 h-full bg-accent-light shadow-[0_0_4px_#7c3aed]" />
            <div className="absolute -top-1 -left-[5px] w-3 h-3 bg-accent-light border-2 border-bg rounded-full shadow-[0_0_6px_#7c3aed]" />
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 pl-[60px]">
        <span className="text-[10px] text-text-muted font-semibold">{fmt(currentTime)}</span>
        <span className="text-[10px] text-text-muted">/ {fmt(duration || 0)}</span>
      </div>
    </div>
  )
}
