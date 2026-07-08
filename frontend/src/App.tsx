import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, useSearchParams } from 'react-router-dom'
import styles from './App.module.css'
import { JobsPage } from './jobs/JobsPage'
import { SavedSearchesPage } from './searches/SavedSearchesPage'

const queryClient = new QueryClient()

type View = 'jobs' | 'searches'

function AppShell() {
  const [searchParams, setSearchParams] = useSearchParams()
  // View is a URL param so filters set on Jobs survive a hop to Saved searches
  // (that's how "save from current filters" reads them) and the view is shareable.
  const view: View = searchParams.get('view') === 'searches' ? 'searches' : 'jobs'
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
        </nav>
      </aside>
      {view === 'jobs' ? <JobsPage /> : <SavedSearchesPage />}
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
