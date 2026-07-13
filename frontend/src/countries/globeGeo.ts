// Procedural holographic dot-globe geometry — ported verbatim from the Beacon.dc.html
// handoff (2026-07-13). Pure data + math only; the canvas engine lives in Globe.tsx.
// LAND/SEA are real continent outlines traced from Natural Earth 1:110m silhouettes.

export const LAT_TOP = 80
export const LAT_BOT = -56

export type Vec = { X: number; Y: number; Z: number }
export type LonLat = readonly [number, number]

export const JAKARTA = { lon: 106.85, lat: -6.2 }

export const LAND: LonLat[][] = [
  // North America
  [[-166, 66], [-164, 60], [-158, 57], [-152, 59], [-145, 60], [-136, 58], [-131, 53], [-124, 48], [-124, 42], [-122, 37], [-118, 34], [-114, 30], [-110, 24], [-106, 23], [-103, 18], [-96, 16], [-92, 15], [-87, 13], [-83, 9], [-79, 8], [-82, 9], [-83, 15], [-88, 16], [-88, 21], [-91, 19], [-95, 19], [-97, 26], [-94, 29], [-89, 29], [-84, 30], [-81, 25], [-81, 31], [-76, 35], [-74, 40], [-70, 43], [-67, 45], [-64, 45], [-60, 47], [-56, 51], [-64, 54], [-66, 60], [-78, 62], [-82, 73], [-90, 70], [-100, 69], [-115, 70], [-128, 70], [-140, 70], [-156, 71], [-165, 68]],
  // Greenland
  [[-46, 60], [-50, 64], [-53, 66], [-51, 70], [-42, 74], [-30, 76], [-20, 74], [-22, 70], [-32, 68], [-42, 64]],
  // South America
  [[-79, 8], [-77, 1], [-81, -5], [-77, -12], [-71, -18], [-70, -23], [-71, -30], [-73, -37], [-74, -45], [-72, -52], [-69, -55], [-65, -54], [-62, -49], [-63, -42], [-62, -40], [-57, -38], [-57, -35], [-53, -34], [-48, -28], [-43, -23], [-39, -18], [-39, -13], [-35, -8], [-38, -4], [-44, -2], [-50, 0], [-51, 4], [-58, 6], [-62, 8], [-66, 11], [-72, 12], [-75, 9]],
  // Africa
  [[-17, 15], [-16, 12], [-11, 7], [-4, 5], [3, 6], [9, 4], [9, 2], [11, -2], [13, -6], [12, -16], [15, -27], [18, -34], [22, -34], [27, -33], [32, -29], [35, -24], [40, -16], [40, -11], [40, -3], [43, -1], [48, 5], [51, 11], [48, 11], [44, 11], [43, 12], [40, 15], [37, 18], [35, 24], [34, 28], [32, 31], [25, 32], [19, 30], [15, 32], [10, 34], [8, 37], [3, 37], [-2, 35], [-6, 36], [-10, 30], [-13, 27], [-17, 21]],
  // Eurasia
  [[-9, 37], [-6, 36], [-2, 37], [0, 39], [3, 42], [7, 43], [10, 44], [13, 41], [16, 38], [18, 40], [13, 45], [13, 44], [15, 44], [19, 42], [23, 40], [24, 38], [27, 40], [30, 40], [36, 36], [36, 33], [35, 31], [34, 28], [35, 28], [39, 21], [43, 13], [48, 14], [52, 17], [57, 22], [59, 25], [61, 25], [67, 25], [70, 21], [73, 16], [74, 12], [77, 8], [80, 13], [80, 16], [84, 19], [87, 21], [90, 22], [92, 21], [94, 16], [98, 10], [104, 1], [105, 10], [109, 12], [109, 16], [107, 20], [108, 21], [110, 21], [114, 22], [117, 24], [120, 25], [121, 29], [122, 31], [120, 34], [122, 37], [122, 41], [125, 40], [126, 40], [126, 37], [126, 34], [129, 35], [129, 38], [131, 43], [135, 47], [138, 54], [142, 54], [141, 59], [153, 59], [156, 51], [162, 56], [163, 61], [170, 60], [175, 62], [180, 66], [178, 69], [160, 70], [145, 72], [135, 73], [113, 74], [105, 77], [95, 76], [80, 73], [73, 72], [68, 68], [60, 69], [55, 68], [50, 69], [44, 66], [40, 66], [35, 66], [33, 69], [28, 71], [25, 71], [20, 70], [16, 69], [13, 66], [8, 63], [5, 61], [5, 58], [6, 58], [8, 58], [8, 57], [8, 55], [9, 54], [7, 53], [4, 52], [2, 51], [1, 50], [0, 49], [-2, 48], [-5, 48], [-2, 47], [-1, 46], [-2, 44], [-2, 43], [-9, 43], [-9, 41], [-9, 38]],
  // Great Britain
  [[-5, 50], [-3, 51], [-3, 53], [-4, 54], [-5, 55], [-6, 56], [-5, 58], [-3, 58], [-2, 57], [0, 53], [1, 52], [1, 51], [-1, 51]],
  // Ireland
  [[-10, 52], [-10, 54], [-8, 55], [-6, 55], [-6, 52], [-9, 51]],
  // Iceland
  [[-24, 65], [-22, 66], [-14, 66], [-13, 64], [-19, 63]],
  // Japan
  [[130, 31], [131, 34], [133, 36], [137, 37], [140, 40], [142, 40], [141, 42], [144, 43], [145, 44], [143, 42], [140, 38], [140, 35], [137, 34], [135, 34], [132, 33]],
  // Australia
  [[114, -22], [113, -26], [115, -34], [118, -35], [123, -34], [129, -32], [134, -33], [138, -35], [140, -38], [143, -39], [148, -38], [150, -37], [153, -32], [153, -28], [151, -24], [149, -21], [146, -19], [145, -15], [142, -11], [141, -13], [139, -17], [136, -12], [132, -11], [129, -15], [126, -14], [122, -18], [121, -20], [119, -20]],
  // Tasmania
  [[145, -41], [148, -41], [148, -43], [146, -43]],
  // New Zealand — North
  [[173, -35], [175, -37], [178, -38], [177, -40], [174, -41], [173, -39]],
  // New Zealand — South
  [[171, -41], [174, -42], [173, -44], [171, -46], [167, -46], [168, -44]],
  // Madagascar
  [[49, -13], [50, -15], [48, -25], [45, -25], [43, -22], [44, -16], [47, -13]],
  // Sumatra
  [[95, 5], [98, 4], [104, -2], [106, -6], [100, -3], [95, 2]],
  // Java
  [[105, -6], [114, -7], [114, -8], [106, -8]],
  // Borneo
  [[109, 2], [117, 4], [119, -1], [116, -4], [110, -3], [109, 1]],
  // Sulawesi
  [[119, 1], [123, 1], [125, -2], [121, -5], [120, -3]],
  // New Guinea
  [[131, -1], [141, -3], [150, -6], [147, -8], [138, -8], [132, -4]],
  // Philippines
  [[120, 14], [124, 18], [126, 14], [125, 10], [122, 7], [120, 10]],
  // Sri Lanka
  [[80, 9], [82, 8], [81, 6], [80, 7]],
  // Cuba
  [[-84, 22], [-80, 23], [-74, 20], [-78, 20]],
]

// Inland seas / bays punched out of the filled land mask.
export const SEA: LonLat[][] = [
  [[-95, 60], [-82, 60], [-78, 56], [-80, 51], [-88, 51], [-95, 57]], // Hudson Bay
  [[12, 55], [20, 55], [26, 60], [25, 66], [20, 63], [17, 59], [14, 56]], // Baltic + Gulf of Bothnia
  [[28, 41], [41, 41], [42, 45], [33, 47], [28, 45]], // Black Sea
  [[47, 37], [54, 38], [53, 47], [48, 46], [47, 42]], // Caspian Sea
  [[48, 30], [57, 27], [56, 24], [50, 24], [48, 29]], // Persian Gulf
]

// Pin coordinates + primary flag, keyed by ISO code (the backend's Country.code).
// lat/lon are the prototype's exact PINS values so the globe matches the handoff.
export const PIN_GEO: Record<string, { lat: number; lon: number }> = {
  US: { lat: 38, lon: -120 },
  CA: { lat: 53, lon: -101 },
  IE: { lat: 53.3, lon: -8 },
  NL: { lat: 52.3, lon: 5 },
  SE: { lat: 61, lon: 15 },
  SG: { lat: 1.3, lon: 103.8 },
  JP: { lat: 37, lon: 139 },
  AU: { lat: -27, lon: 134 },
  NO: { lat: 60, lon: 10.7 },
  DK: { lat: 55.7, lon: 12.5 },
  CH: { lat: 47.4, lon: 8.5 },
}

export function px(lon: number, W: number): number {
  return ((lon + 180) / 360) * W
}
export function py(lat: number, H: number): number {
  return ((LAT_TOP - lat) / (LAT_TOP - LAT_BOT)) * H
}

export function llToVec(lon: number, lat: number): Vec {
  const la = (lat * Math.PI) / 180
  const lo = (lon * Math.PI) / 180
  return { X: Math.cos(la) * Math.sin(lo), Y: Math.sin(la), Z: Math.cos(la) * Math.cos(lo) }
}

// Project a lon/lat to a unit sphere vector, rotated by yaw (about Y) then tilted by pitch.
export function project(lon: number, lat: number, yaw: number, pitch: number): Vec {
  const la = (lat * Math.PI) / 180
  const lo = ((lon + yaw) * Math.PI) / 180
  const X = Math.cos(la) * Math.sin(lo)
  const Y0 = Math.sin(la)
  const Z0 = Math.cos(la) * Math.cos(lo)
  const t = (pitch * Math.PI) / 180
  const c = Math.cos(t)
  const s = Math.sin(t)
  return { X, Y: Y0 * c - Z0 * s, Z: Y0 * s + Z0 * c }
}

// Project a pre-computed unit vector (used for the beacon arc / origin marker).
export function projectVec(v: Vec, yaw: number, pitch: number): Vec {
  const ps = (yaw * Math.PI) / 180
  const t = (pitch * Math.PI) / 180
  const cp = Math.cos(ps)
  const sp = Math.sin(ps)
  const X1 = v.X * cp + v.Z * sp
  const Z1 = -v.X * sp + v.Z * cp
  const Y1 = v.Y
  const c = Math.cos(t)
  const s = Math.sin(t)
  return { X: X1, Y: Y1 * c - Z1 * s, Z: Y1 * s + Z1 * c }
}

export function slerp(a: Vec, b: Vec, f: number): Vec {
  let d = a.X * b.X + a.Y * b.Y + a.Z * b.Z
  d = Math.max(-1, Math.min(1, d))
  const om = Math.acos(d)
  if (om < 1e-4) return { X: a.X, Y: a.Y, Z: a.Z }
  const s0 = Math.sin((1 - f) * om) / Math.sin(om)
  const s1 = Math.sin(f * om) / Math.sin(om)
  return { X: a.X * s0 + b.X * s1, Y: a.Y * s0 + b.Y * s1, Z: a.Z * s0 + b.Z * s1 }
}
