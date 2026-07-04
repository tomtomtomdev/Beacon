import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import styles from './App.module.css'
import { JobsPage } from './jobs/JobsPage'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <aside className={styles.sidebar}>
          <div className={styles.brand}>
            <h1 className={styles.brandName}>Beacon</h1>
            <span className={styles.brandTag}>job scanner</span>
          </div>
          <nav className={styles.nav}>
            <button type="button" className={styles.navItemActive}>
              Jobs
            </button>
          </nav>
        </aside>
        <JobsPage />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
