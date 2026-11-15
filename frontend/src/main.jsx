import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Link } from 'react-router-dom'
import { WorkspaceProvider } from './context/Workspace'
import { Shell } from './components/Shell'
import { ErrorBoundary, EmptyState, PageHeading } from './components/UI'
import { Home } from './pages/Home'
import { Upload } from './pages/Upload'
import { Analysis } from './pages/Analysis'
import { Job } from './pages/Job'
import { Match } from './pages/Match'
import { History } from './pages/History'
import { Privacy } from './pages/Privacy'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <WorkspaceProvider>
          <Routes>
            <Route element={<Shell />}>
              <Route index element={<Home />} />
              <Route path="upload" element={<Upload />} />
              <Route path="analysis" element={<Analysis />} />
              <Route path="job" element={<Job />} />
              <Route path="match" element={<Match />} />
              <Route path="history" element={<History />} />
              <Route path="privacy" element={<Privacy />} />
              <Route
                path="*"
                element={
                  <>
                    <PageHeading title="Page not found" />
                    <EmptyState
                      title="Let’s get you back on track"
                      to="/"
                      label="Go to overview"
                    >
                      This page does not exist.{' '}
                      <Link to="/upload">Start a new analysis</Link> or return
                      to the overview.
                    </EmptyState>
                  </>
                }
              />
            </Route>
          </Routes>
        </WorkspaceProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
)
