import { createContext, useContext, useRef, useState } from 'react'
import { request } from '../lib/api'

const WorkspaceContext = createContext(null)
export function WorkspaceProvider({ children }) {
  const [token, setToken] = useState('')
  const [historyAvailable, setHistoryAvailable] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [match, setMatchState] = useState(null)
  const [job, setJob] = useState('')
  const [sessionOpen, setSessionOpen] = useState(false)
  const epoch = useRef(0)
  const controllers = useRef(new Set())
  function controller() {
    const value = new AbortController()
    controllers.current.add(value)
    value.signal.addEventListener(
      'abort',
      () => controllers.current.delete(value),
      { once: true },
    )
    return value
  }
  function release(value) {
    controllers.current.delete(value)
  }
  function clear() {
    controllers.current.forEach((value) => value.abort())
    controllers.current.clear()
    setAnalysis(null)
    setMatchState(null)
    setJob('')
  }
  function disconnect() {
    epoch.current += 1
    controllers.current.forEach((value) => value.abort())
    controllers.current.clear()
    setToken('')
    setHistoryAvailable(false)
    clear()
  }
  async function connect(value, signal) {
    const current = epoch.current
    let storage = false
    try {
      await request('/api/v1/analyses?limit=1', value, { signal })
      storage = true
    } catch (error) {
      if (error.code !== 'storage_disabled') throw error
    }
    if (signal.aborted || epoch.current !== current) return
    clear()
    setToken(value)
    setHistoryAvailable(storage)
    setSessionOpen(false)
  }
  function acceptAnalysis(value) {
    clear()
    setAnalysis(value)
  }
  function setMatch(value, jobDescription = job) {
    setMatchState(value ? { ...value, job_description: jobDescription } : null)
  }
  return (
    <WorkspaceContext.Provider
      value={{
        token,
        historyAvailable,
        analysis,
        match,
        job,
        setJob,
        setMatch,
        acceptAnalysis,
        clear,
        connect,
        disconnect,
        sessionOpen,
        setSessionOpen,
        controller,
        release,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  )
}
export function useWorkspace() {
  return useContext(WorkspaceContext)
}
