import { useQuery } from '@tanstack/react-query'
import { Globe } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { fetchCountries } from '../api/countries'
import type { Country } from '../api/types'
import styles from './CountriesPage.module.css'

const TIER_LABEL: Record<Country['priority_tier'], string> = {
  primary: 'Primary',
  nice_to_have: 'Nice-to-have',
}

// Approximate lon/lat per target country (capital / HQ metro) for equirectangular pin placement.
const PIN_COORDS: Record<string, { lon: number; lat: number }> = {
  SG: { lon: 103.8, lat: 1.35 },
  JP: { lon: 139.7, lat: 35.7 },
  AU: { lon: 151.2, lat: -33.9 },
  NL: { lon: 4.9, lat: 52.4 },
  US: { lon: -122.4, lat: 37.8 },
  CA: { lon: -79.4, lat: 43.7 },
  IE: { lon: -6.3, lat: 53.3 },
  SE: { lon: 18.1, lat: 59.3 },
  NO: { lon: 10.7, lat: 59.9 },
  DK: { lon: 12.6, lat: 55.7 },
  CH: { lon: 8.5, lat: 47.4 },
}

// Equirectangular projection → percentage offsets inside the map box.
function pinPosition(lon: number, lat: number): { left: string; top: string } {
  return { left: `${((lon + 180) / 360) * 100}%`, top: `${((90 - lat) / 180) * 100}%` }
}

export function CountriesPage() {
  const { data: countries, isPending, isError } = useQuery({
    queryKey: ['countries'],
    queryFn: fetchCountries,
  })
  // Which country is highlighted — transient UI state, so local (not a shareable URL param).
  const [selected, setSelected] = useState<string | null>(null)
  const toggle = (code: string) => setSelected((current) => (current === code ? null : code))

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1 className={styles.h1}>Country &amp; visa reference</h1>
        <p className={styles.subtitle}>
          Figures are as-known and change — each card carries its verified date. PR and
          citizenship differ: Indonesia bars adult dual citizenship, so PR is often the endpoint.
        </p>
      </header>

      {isError && <p className={styles.state}>Could not reach the Beacon API.</p>}
      {isPending && <p className={styles.state}>Loading…</p>}

      {countries && (
        <>
          <TargetGeography countries={countries} selected={selected} onSelect={toggle} />
          <div className={styles.grid}>
            {countries.map((country) => (
              <CountryCard
                key={country.code}
                country={country}
                selected={selected === country.code}
                onSelect={() => toggle(country.code)}
              />
            ))}
          </div>
        </>
      )}
    </main>
  )
}

function TargetGeography({
  countries,
  selected,
  onSelect,
}: {
  countries: Country[]
  selected: string | null
  onSelect: (code: string) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  // Draw the decorative land-dot grid backdrop. Canvas is an external system → effect.
  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return // jsdom has no 2d context — pins (DOM) still render/testable
    const { width, height } = canvas
    ctx.clearRect(0, 0, width, height)
    ctx.fillStyle = getComputedStyle(canvas).getPropertyValue('--map-land') || '#cdd6db'
    const step = 14
    for (let y = step; y < height; y += step) {
      for (let x = step; x < width; x += step) {
        ctx.beginPath()
        ctx.arc(x, y, 1.1, 0, Math.PI * 2)
        ctx.fill()
      }
    }
  }, [])

  return (
    <section className={styles.geoPanel}>
      <div className={styles.geoHeader}>
        <Globe size={16} aria-hidden />
        Target geography
        <span className={styles.legend}>
          <span className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.dotPrimary}`} /> Primary target
          </span>
          <span className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.dotNice}`} /> Nice-to-have
          </span>
        </span>
      </div>
      <div className={styles.map}>
        <canvas ref={canvasRef} width={720} height={300} className={styles.canvas} />
        {countries.map((country) => {
          const coords = PIN_COORDS[country.code]
          if (!coords) return null
          const isSelected = selected === country.code
          const tierClass = country.priority_tier === 'primary' ? styles.pinPrimary : styles.pinNice
          return (
            <button
              key={country.code}
              type="button"
              className={`${styles.pin} ${tierClass} ${isSelected ? styles.pinActive : ''}`}
              style={pinPosition(coords.lon, coords.lat)}
              aria-label={`${country.name} on map`}
              aria-pressed={isSelected}
              onClick={() => onSelect(country.code)}
            />
          )
        })}
      </div>
    </section>
  )
}

function CountryCard({
  country,
  selected,
  onSelect,
}: {
  country: Country
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={`${styles.card} ${selected ? styles.cardSelected : ''}`}
      aria-label={`${country.name} details`}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <div className={styles.cardHeader}>
        <span className={styles.cardName}>{country.name}</span>
        <span
          className={`${styles.tierPill} ${
            country.priority_tier === 'primary' ? styles.tierPrimary : styles.tierNice
          }`}
        >
          {TIER_LABEL[country.priority_tier]}
        </span>
      </div>
      <div className={styles.block}>
        <div className={styles.blockLabel}>Work visa</div>
        <div className={styles.blockValue}>{country.visa_summary}</div>
      </div>
      <div className={styles.block}>
        <div className={styles.blockLabel}>PR path</div>
        <div className={styles.blockValue}>{country.pr_summary}</div>
      </div>
      <div className={styles.block}>
        <div className={styles.blockLabel}>Citizenship</div>
        <div className={styles.blockValue}>{country.citizenship_summary}</div>
      </div>
      <div className={styles.cardFooter}>
        <span className={styles.registryNote}>{country.registry_name}</span>
        <span className={styles.verified}>✓ {country.verified_at}</span>
      </div>
    </button>
  )
}
