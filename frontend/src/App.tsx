import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, useSearchParams } from 'react-router-dom'
import styles from './App.module.css'
import { CompaniesPage } from './companies/CompaniesPage'
import { CountriesPage } from './countries/CountriesPage'
import { JobsPage } from './jobs/JobsPage'
import { SavedSearchesPage } from './searches/SavedSearchesPage'
import { SettingsPage } from './settings/SettingsPage'

const queryClient = new QueryClient()

type View = 'jobs' | 'searches' | 'companies' | 'countries' | 'settings'

const VIEWS: readonly View[] = ['jobs', 'searches', 'companies', 'countries', 'settings']

function parseView(raw: string | null): View {
  return VIEWS.includes(raw as View) ? (raw as View) : 'jobs'
}

function AppShell() {
  const [searchParams, setSearchParams] = useSearchParams()
  // View is a URL param so filters set on Jobs survive a hop to Saved searches
  // (that's how "save from current filters" reads them) and the view is shareable.
  const view: View = parseView(searchParams.get('view'))
  const setView = (next: View) =>
    setSearchParams(
      (params) => {
        if (next === 'jobs') params.delete('view')
        else params.set('view', next)
        return params
      },
      { replace: true },
    )

  return (
    <>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <h1 className={styles.brandName}>Beacon</h1>
          <span className={styles.brandTag}>job scanner</span>
        </div>
        <nav className={styles.nav}>
          <button
            type="button"
            className={view === 'jobs' ? styles.navItemActive : styles.navItem}
            aria-current={view === 'jobs'}
            onClick={() => setView('jobs')}
          >
            Jobs
          </button>
          <button
            type="button"
            className={view === 'searches' ? styles.navItemActive : styles.navItem}
            aria-current={view === 'searches'}
            onClick={() => setView('searches')}
          >
            Saved searches
          </button>
          <button
            type="button"
            className={view === 'companies' ? styles.navItemActive : styles.navItem}
            aria-current={view === 'companies'}
            onClick={() => setView('companies')}
          >
            Companies
          </button>
          <button
            type="button"
            className={view === 'countries' ? styles.navItemActive : styles.navItem}
            aria-current={view === 'countries'}
            onClick={() => setView('countries')}
          >
            Countries
          </button>
          <button
            type="button"
            className={view === 'settings' ? styles.navItemActive : styles.navItem}
            aria-current={view === 'settings'}
            onClick={() => setView('settings')}
          >
            Settings
          </button>
        </nav>
      </aside>
      {view === 'jobs' && <JobsPage />}
      {view === 'searches' && <SavedSearchesPage />}
      {view === 'companies' && <CompaniesPage />}
      {view === 'countries' && <CountriesPage />}
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
