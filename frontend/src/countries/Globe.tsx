import { useEffect, useMemo, useRef } from 'react'
import type { Country } from '../api/types'
import styles from './CountriesPage.module.css'
import {
  JAKARTA,
  LAND,
  LAT_BOT,
  LAT_TOP,
  llToVec,
  PIN_GEO,
  project,
  projectVec,
  px,
  py,
  SEA,
  slerp,
  type Vec,
} from './globeGeo'

type Pin = { code: string; name: string; lat: number; lon: number; primary: boolean }
type PinScreen = { code: string; name: string; x: number; y: number }
type GlState = {
  yaw: number
  pitch: number
  spin: number
  dragging: boolean
  moved: boolean
  lx: number
  ly: number
  hover: string | null
  pinScreens: PinScreen[]
}

// Land point cloud is built once from the mask and cached — it never changes.
let landPtsCache: [number, number][] | null = null

function buildLandPts(): [number, number][] {
  if (landPtsCache) return landPtsCache
  const W = 1024
  const H = Math.round((1024 * (LAT_TOP - LAT_BOT)) / 360)
  const m = document.createElement('canvas')
  m.width = W
  m.height = H
  const g = m.getContext('2d')
  if (!g) return []
  const trace = (poly: readonly (readonly [number, number])[]) => {
    g.beginPath()
    poly.forEach((pt, i) => {
      const x = px(pt[0], W)
      const y = py(pt[1], H)
      if (i === 0) g.moveTo(x, y)
      else g.lineTo(x, y)
    })
    g.closePath()
  }
  g.fillStyle = '#000'
  for (const poly of LAND) {
    trace(poly)
    g.fill()
  }
  g.globalCompositeOperation = 'destination-out'
  for (const poly of SEA) {
    trace(poly)
    g.fill()
  }
  g.globalCompositeOperation = 'source-over'
  const mask = g.getImageData(0, 0, W, H).data
  const isLand = (lon: number, lat: number) => {
    const x = Math.floor(px(lon, W))
    const y = Math.floor(py(lat, H))
    if (x < 0 || y < 0 || x >= W || y >= H) return false
    return mask[(y * W + x) * 4 + 3] > 128
  }
  const pts: [number, number][] = []
  const step = 2.0
  for (let lat = LAT_BOT; lat <= LAT_TOP; lat += step)
    for (let lon = -180; lon <= 180; lon += step) if (isLand(lon, lat)) pts.push([lon, lat])
  landPtsCache = pts
  return pts
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

function renderGlobe(
  ctx: CanvasRenderingContext2D,
  cv: HTMLCanvasElement,
  g: GlState,
  landPts: [number, number][],
  pins: Pin[],
  selectedCode: string | null,
) {
  const selPin = selectedCode ? pins.find((p) => p.code === selectedCode) : null
  if (selPin) {
    if (!g.dragging) {
      // Center on the great-circle midpoint between Jakarta and the destination.
      const va = llToVec(JAKARTA.lon, JAKARTA.lat)
      const vb = llToVec(selPin.lon, selPin.lat)
      const m = slerp(va, vb, 0.5)
      const mLon = (Math.atan2(m.X, m.Z) * 180) / Math.PI
      const mLat = (Math.asin(Math.max(-1, Math.min(1, m.Y))) * 180) / Math.PI
      const dy = (((-mLon - g.yaw + 540) % 360) - 180)
      g.yaw += dy * 0.1
      g.pitch += (mLat * 0.6 - g.pitch) * 0.1
    }
  } else if (!g.dragging) {
    g.yaw += g.spin
  }

  const dpr = window.devicePixelRatio || 1
  const w = cv.clientWidth
  const h = cv.clientHeight
  if (!w || !h) return
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
    cv.width = Math.round(w * dpr)
    cv.height = Math.round(h * dpr)
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)
  const cx = w / 2
  const cy = h / 2
  const R = Math.min(w, h) * 0.62
  const now = performance.now() / 1000

  // atmosphere
  const glow = ctx.createRadialGradient(cx, cy, R * 0.7, cx, cy, R * 1.3)
  glow.addColorStop(0, 'rgba(45,212,191,0)')
  glow.addColorStop(0.55, 'rgba(45,212,191,0.11)')
  glow.addColorStop(0.82, 'rgba(45,212,191,0.05)')
  glow.addColorStop(1, 'rgba(45,212,191,0)')
  ctx.fillStyle = glow
  ctx.beginPath()
  ctx.arc(cx, cy, R * 1.3, 0, 6.2832)
  ctx.fill()

  // globe face
  const face = ctx.createRadialGradient(cx - R * 0.32, cy - R * 0.36, R * 0.06, cx, cy, R)
  face.addColorStop(0, 'rgba(15,70,76,0.62)')
  face.addColorStop(1, 'rgba(4,20,27,0.5)')
  ctx.beginPath()
  ctx.arc(cx, cy, R, 0, 6.2832)
  ctx.fillStyle = face
  ctx.fill()

  // graticule
  ctx.lineWidth = 1
  const drawLine = (pts: Vec[]) => {
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i]
      const b = pts[i + 1]
      const fr = a.Z > 0 && b.Z > 0
      ctx.strokeStyle = fr ? 'rgba(94,234,212,0.13)' : 'rgba(94,234,212,0.04)'
      ctx.beginPath()
      ctx.moveTo(cx + a.X * R, cy - a.Y * R)
      ctx.lineTo(cx + b.X * R, cy - b.Y * R)
      ctx.stroke()
    }
  }
  for (let lon = -180; lon < 180; lon += 30) {
    const pts: Vec[] = []
    for (let lat = -80; lat <= 80; lat += 4) pts.push(project(lon, lat, g.yaw, g.pitch))
    drawLine(pts)
  }
  for (let lat = -60; lat <= 80; lat += 20) {
    const pts: Vec[] = []
    for (let lon = -180; lon <= 180; lon += 6) pts.push(project(lon, lat, g.yaw, g.pitch))
    drawLine(pts)
  }

  // land dots
  for (const ll of landPts) {
    const p = project(ll[0], ll[1], g.yaw, g.pitch)
    if (p.Z <= 0) continue
    const b = 0.28 + 0.64 * p.Z
    ctx.beginPath()
    ctx.arc(cx + p.X * R, cy - p.Y * R, 1.35, 0, 6.2832)
    ctx.fillStyle = 'rgba(94,234,212,' + b.toFixed(2) + ')'
    ctx.fill()
  }

  // rim
  ctx.lineWidth = 1.4
  ctx.strokeStyle = 'rgba(94,234,212,0.42)'
  ctx.beginPath()
  ctx.arc(cx, cy, R, 0, 6.2832)
  ctx.stroke()

  // beacon arc: Jakarta -> selected country
  if (selPin) {
    const va = llToVec(JAKARTA.lon, JAKARTA.lat)
    const vb = llToVec(selPin.lon, selPin.lat)
    const N = 90
    const pts: { x: number; y: number; z: number }[] = []
    for (let i = 0; i <= N; i++) {
      const f = i / N
      const v = slerp(va, vb, f)
      const lift = 1 + 0.22 * Math.sin(Math.PI * f)
      const p = projectVec(v, g.yaw, g.pitch)
      pts.push({ x: cx + p.X * R * lift, y: cy - p.Y * R * lift, z: p.Z })
    }
    ctx.lineCap = 'round'
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i]
      const b = pts[i + 1]
      if (a.z < -0.1 && b.z < -0.1) continue
      const front = (a.z + b.z) / 2 > 0
      ctx.strokeStyle = front ? 'rgba(94,234,212,0.9)' : 'rgba(94,234,212,0.16)'
      ctx.lineWidth = front ? 2.2 : 1.1
      ctx.beginPath()
      ctx.moveTo(a.x, a.y)
      ctx.lineTo(b.x, b.y)
      ctx.stroke()
    }
    // travelling pulse
    const tf = (now * 0.32) % 1
    const vp = slerp(va, vb, tf)
    const lp = 1 + 0.22 * Math.sin(Math.PI * tf)
    const pp = projectVec(vp, g.yaw, g.pitch)
    if (pp.Z > -0.05) {
      const pxp = cx + pp.X * R * lp
      const pyp = cy - pp.Y * R * lp
      ctx.shadowColor = '#5eead4'
      ctx.shadowBlur = 14
      ctx.beginPath()
      ctx.arc(pxp, pyp, 3.2, 0, 6.2832)
      ctx.fillStyle = '#eafffb'
      ctx.fill()
      ctx.shadowBlur = 0
    }
    // origin marker: Jakarta
    const op = projectVec(va, g.yaw, g.pitch)
    if (op.Z > 0) {
      const ox = cx + op.X * R
      const oy = cy - op.Y * R
      ctx.shadowColor = '#fcd34d'
      ctx.shadowBlur = 10
      ctx.beginPath()
      ctx.arc(ox, oy, 3.6, 0, 6.2832)
      ctx.fillStyle = '#fcd34d'
      ctx.fill()
      ctx.shadowBlur = 0
      ctx.beginPath()
      ctx.arc(ox, oy, 3.6, 0, 6.2832)
      ctx.lineWidth = 1.3
      ctx.strokeStyle = 'rgba(255,255,255,0.9)'
      ctx.stroke()
      ctx.font = '600 10.5px Geist, sans-serif'
      ctx.textBaseline = 'middle'
      ctx.textAlign = 'start'
      const tw = ctx.measureText('Jakarta').width
      ctx.fillStyle = 'rgba(4,20,27,0.62)'
      roundRect(ctx, ox + 9, oy - 9, tw + 12, 18, 5)
      ctx.fill()
      ctx.fillStyle = '#fde9b0'
      ctx.fillText('Jakarta', ox + 15, oy + 0.5)
    }
  }

  // pins
  g.pinScreens = []
  ctx.font = '600 11px Geist, sans-serif'
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'start'
  for (const pin of pins) {
    const p = project(pin.lon, pin.lat, g.yaw, g.pitch)
    const front = p.Z > 0.02
    const sx = cx + p.X * R
    const sy = cy - p.Y * R
    if (front) g.pinScreens.push({ code: pin.code, name: pin.name, x: sx, y: sy })
    const primary = pin.primary
    const on = selectedCode === pin.code || g.hover === pin.code
    const col = primary ? '#5eead4' : '#9fb6bb'
    if (!front) {
      ctx.globalAlpha = 0.26
      ctx.beginPath()
      ctx.arc(sx, sy, 2.2, 0, 6.2832)
      ctx.fillStyle = col
      ctx.fill()
      ctx.globalAlpha = 1
      continue
    }
    const ph = (now * 0.5 + Math.abs(pin.lon) * 0.004) % 1
    const pr = 4 + ph * 13
    ctx.beginPath()
    ctx.arc(sx, sy, pr, 0, 6.2832)
    ctx.strokeStyle = 'rgba(94,234,212,' + (0.45 * (1 - ph)).toFixed(2) + ')'
    ctx.lineWidth = 1.3
    ctx.stroke()
    ctx.shadowColor = col
    ctx.shadowBlur = on ? 18 : 10
    ctx.beginPath()
    ctx.arc(sx, sy, on ? 5 : 3.6, 0, 6.2832)
    ctx.fillStyle = col
    ctx.fill()
    ctx.shadowBlur = 0
    ctx.beginPath()
    ctx.arc(sx, sy, on ? 5 : 3.6, 0, 6.2832)
    ctx.lineWidth = 1.3
    ctx.strokeStyle = 'rgba(255,255,255,0.85)'
    ctx.stroke()
    if (primary || on) {
      const tw = ctx.measureText(pin.name).width
      const left = p.X > 0.12
      const tx = left ? sx - 14 - tw : sx + 14
      ctx.fillStyle = on ? 'rgba(94,234,212,0.22)' : 'rgba(4,20,27,0.6)'
      roundRect(ctx, tx - 6, sy - 9, tw + 12, 18, 5)
      ctx.fill()
      ctx.fillStyle = on ? '#eafffb' : '#c4ebe4'
      ctx.fillText(pin.name, tx, sy + 0.5)
    }
  }
}

export function Globe({
  countries,
  selectedCode,
  onSelect,
}: {
  countries: Country[]
  selectedCode: string | null
  onSelect: (code: string | null) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const pins = useMemo<Pin[]>(
    () =>
      countries
        .map((c) => {
          const geo = PIN_GEO[c.code]
          return geo
            ? { code: c.code, name: c.name, lat: geo.lat, lon: geo.lon, primary: c.priority_tier === 'primary' }
            : null
        })
        .filter((p): p is Pin => p !== null),
    [countries],
  )

  // Latest props kept in refs so the animation loop reads current values without re-subscribing.
  const pinsRef = useRef(pins)
  const selectedRef = useRef(selectedCode)
  const onSelectRef = useRef(onSelect)
  useEffect(() => {
    pinsRef.current = pins
  }, [pins])
  useEffect(() => {
    selectedRef.current = selectedCode
  }, [selectedCode])
  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  // The canvas is an external system: subscribe on mount, tear down on unmount.
  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return // jsdom has no 2d context — the a11y buttons still render/select
    const landPts = buildLandPts()
    const gl: GlState = {
      yaw: 18,
      pitch: -20,
      spin: 0.035,
      dragging: false,
      moved: false,
      lx: 0,
      ly: 0,
      hover: null,
      pinScreens: [],
    }
    const pos = (e: PointerEvent) => {
      const r = canvas.getBoundingClientRect()
      return { x: e.clientX - r.left, y: e.clientY - r.top }
    }
    const hitPin = (x: number, y: number): PinScreen | null => {
      let best: PinScreen | null = null
      let bd = 1e9
      for (const p of gl.pinScreens) {
        const d = Math.hypot(p.x - x, p.y - y)
        if (d < 15 && d < bd) {
          bd = d
          best = p
        }
      }
      return best
    }
    const onDown = (e: PointerEvent) => {
      gl.dragging = true
      gl.moved = false
      const p = pos(e)
      gl.lx = p.x
      gl.ly = p.y
      try {
        canvas.setPointerCapture(e.pointerId)
      } catch {
        /* ignore */
      }
    }
    const onMove = (e: PointerEvent) => {
      const p = pos(e)
      if (gl.dragging) {
        const dx = p.x - gl.lx
        const dy = p.y - gl.ly
        if (Math.abs(dx) + Math.abs(dy) > 3) gl.moved = true
        gl.yaw += dx * 0.45
        gl.pitch = Math.max(-82, Math.min(82, gl.pitch - dy * 0.3))
        gl.lx = p.x
        gl.ly = p.y
      } else {
        const hit = hitPin(p.x, p.y)
        canvas.style.cursor = hit ? 'pointer' : 'grab'
        gl.hover = hit ? hit.code : null
      }
    }
    const onUp = (e: PointerEvent) => {
      if (gl.dragging && !gl.moved) {
        const p = pos(e)
        const hit = hitPin(p.x, p.y)
        if (hit) onSelectRef.current(hit.code)
        else onSelectRef.current(null)
      }
      gl.dragging = false
    }
    const onLeave = () => {
      gl.dragging = false
      gl.hover = null
    }
    canvas.addEventListener('pointerdown', onDown)
    canvas.addEventListener('pointermove', onMove)
    canvas.addEventListener('pointerup', onUp)
    canvas.addEventListener('pointerleave', onLeave)
    canvas.style.cursor = 'grab'

    let raf = 0
    const loop = () => {
      renderGlobe(ctx, canvas, gl, landPts, pinsRef.current, selectedRef.current)
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => {
      cancelAnimationFrame(raf)
      canvas.removeEventListener('pointerdown', onDown)
      canvas.removeEventListener('pointermove', onMove)
      canvas.removeEventListener('pointerup', onUp)
      canvas.removeEventListener('pointerleave', onLeave)
    }
  }, [])

  return (
    <>
      <canvas ref={canvasRef} className={styles.canvas} />
      {/* Visually-hidden pin controls: keyboard access + a testable selection surface,
          since the canvas engine handles mouse hit-testing only. */}
      <div className={styles.srPins}>
        {pins.map((pin) => (
          <button
            key={pin.code}
            type="button"
            aria-label={`${pin.name} on globe`}
            aria-pressed={selectedCode === pin.code}
            onClick={() => onSelect(selectedCode === pin.code ? null : pin.code)}
          >
            {pin.name}
          </button>
        ))}
      </div>
    </>
  )
}
