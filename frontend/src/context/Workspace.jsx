import { createContext, useContext, useRef, useState } from 'react'

const WorkspaceContext = createContext(null)
export function WorkspaceProvider({ children }) {
  const [analysis, setAnalysis] = useState(null)
  const [match, setMatchState] = useState(null)
  const [job, setJob] = useState('')
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
        analysis,
        match,
        job,
        setJob,
        setMatch,
        acceptAnalysis,
        clear,
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
