import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Bookmark, Globe, Settings } from 'lucide-react'
import { BrowserRouter, useSearchParams } from 'react-router-dom'
import styles from './App.module.css'
import { CountriesPage } from './countries/CountriesPage'
import { SavedSearchesPage } from './searches/SavedSearchesPage'
import { SettingsPage } from './settings/SettingsPage'

const queryClient = new QueryClient()

// The main area shows one of three views. Countries is home; the Jobs list is not its own
// view — it is a pane inside Countries, gated by a selected country (?focus=).
type View = 'countries' | 'searches' | 'settings'

const VIEWS: readonly View[] = ['countries', 'searches', 'settings']

function parseView(raw: string | null): View {
  return VIEWS.includes(raw as View) ? (raw as View) : 'countries'
}

function AppShell() {
  const [searchParams, setSearchParams] = useSearchParams()
  const view: View = parseView(searchParams.get('view'))

  const goTo = (next: View) =>
    setSearchParams(
      (params) => {
        if (next === 'countries') {
          params.delete('view')
          // Returning to the globe home clears any selected-country jobs pane.
          params.delete('focus')
          params.delete('country')
          params.delete('status')
        } else {
          params.set('view', next)
        }
        return params
      },
      { replace: true },
    )

  return (
    <>
      <aside className={styles.rail}>
        <div className={styles.brand}>
          <svg
            className={styles.brandGlyph}
            width="26"
            height="26"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            aria-hidden
          >
            <circle cx="12" cy="13" r="2.4" fill="currentColor" stroke="none" />
            <path d="M6.5 7.5a8 8 0 000 11" />
            <path d="M17.5 7.5a8 8 0 010 11" />
            <path d="M9.2 10a4 4 0 000 6" />
            <path d="M14.8 10a4 4 0 010 6" />
          </svg>
          <span className={styles.brandName}>Beacon</span>
        </div>

        <nav className={styles.nav}>
          <button
            type="button"
            className={view === 'countries' ? styles.navItemActive : styles.navItem}
            aria-current={view === 'countries'}
            onClick={() => goTo('countries')}
          >
            <Globe size={19} aria-hidden />
            <span className={styles.navLabel}>Globe</span>
          </button>
          <button
            type="button"
            className={view === 'searches' ? styles.navItemActive : styles.navItem}
            aria-current={view === 'searches'}
            onClick={() => goTo('searches')}
          >
            <span className={styles.navIconWrap}>
              <Bookmark size={19} aria-hidden />
              <span className={styles.navBadge}>4</span>
            </span>
            <span className={styles.navLabel}>Saved</span>
          </button>
        </nav>

        <div className={styles.footer}>
          <button
            type="button"
            className={view === 'settings' ? styles.navItemActive : styles.navItem}
            aria-current={view === 'settings'}
            aria-label="Settings"
            onClick={() => goTo('settings')}
          >
            <Settings size={18} aria-hidden />
          </button>
          <div className={styles.liveTag}>07:04 · LIVE</div>
        </div>
      </aside>

      {view === 'countries' && <CountriesPage />}
      {view === 'searches' && <SavedSearchesPage />}
      {view === 'settings' && <SettingsPage />}
    </>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
