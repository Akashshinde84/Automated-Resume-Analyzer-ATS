export const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/+$/, '')
const configuredLimit = Number(import.meta.env.VITE_MAX_UPLOAD_MB || 10)
export const MAX_FILE_BYTES =
  (Number.isFinite(configuredLimit) && configuredLimit > 0
    ? configuredLimit
    : 10) *
  1024 *
  1024

export class ApiError extends Error {
  constructor(message, status = 0, code = 'network_error') {
    super(message)
    this.status = status
    this.code = code
  }
}
export function responseError(data, status) {
  const detail = data?.detail
  const error = new ApiError(
    typeof detail?.message === 'string'
      ? detail.message
      : status === 422
        ? 'Please check the file and input values.'
        : `The request could not be completed (${status}).`,
    status,
    detail?.code,
  )
  if (/^[a-f0-9]{12}$/.test(detail?.diagnostic_id || ''))
    error.diagnosticId = detail.diagnostic_id
  return error
}
export function validateFile(file) {
  if (!file) return 'Choose a PDF or DOCX resume.'
  if (!/\.(pdf|docx)$/i.test(file.name))
    return 'Only PDF and DOCX files are supported.'
  if (!file.size) return 'This file is empty. Choose a resume containing text.'
  if (file.size > MAX_FILE_BYTES)
    return `Choose a file smaller than ${MAX_FILE_BYTES / 1024 / 1024} MB.`
  return null
}
export function safeUrl(value) {
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : null
  } catch {
    return null
  }
}
export function scoreLabel(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${value.toFixed(1)}%`
    : 'Not available'
}

export async function request(
  path,
  { body, method = 'GET', signal, download } = {},
) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      signal,
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
      headers: {
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Cannot reach the API. Check that the backend is running and its CORS settings allow this site.',
    )
  }
  if (response.status === 204) return null
  if (response.ok && download) {
    const expected = download === 'pdf' ? 'application/pdf' : 'application/json'
    if (!response.headers.get('content-type')?.startsWith(expected))
      throw new ApiError(
        'The API returned an unexpected report format. Please retry.',
      )
    return response.blob()
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) throw responseError(data, response.status)
  if (!data) throw new ApiError('The API returned an unreadable response.')
  return data
}

export function reportPayload(analysis, match, format) {
  if (analysis.id || analysis.stored)
    throw new ApiError(
      'Saved analyses are unavailable here. Upload your resume again.',
    )
  const source = { snapshot: analysis }
  if (!match) return { ...source, format }
  if (match.analysis_id !== analysis.id)
    throw new ApiError(
      'This comparison belongs to another analysis. Compare the current resume again.',
    )
  if (match.stored || match.id)
    throw new ApiError(
      'Saved comparisons are unavailable here. Compare your current resume again.',
    )
  return {
    ...source,
    match: {
      id: match.id,
      analysis_id: match.analysis_id,
      stored: match.stored,
      result: match.result,
      report_token: match.report_token,
    },
    job_description: match.job_description,
    format,
  }
}

export function saveDownload(blob, format) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `resume-analysis.${format}`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function uploadResume(file, { region, onProgress, signal }) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/api/v1/resumes/analyze?store=false`)
    xhr.timeout = 180000
    xhr.upload.onprogress = (event) =>
      onProgress(
        event.lengthComputable
          ? Math.round((event.loaded / event.total) * 100)
          : null,
      )
    xhr.upload.onload = () => onProgress(100)
    const abort = () => xhr.abort()
    signal?.addEventListener('abort', abort, { once: true })
    xhr.onloadend = () => signal?.removeEventListener('abort', abort)
    xhr.onload = () => {
      let data
      try {
        data = JSON.parse(xhr.responseText)
      } catch {
        reject(new ApiError('The API returned an unreadable response.'))
        return
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(responseError(data, xhr.status))
    }
    xhr.onerror = () =>
      reject(
        new ApiError(
          'Upload failed. Check your connection, backend, and CORS configuration.',
        ),
      )
    xhr.ontimeout = () =>
      reject(
        new ApiError('Processing timed out. Try a smaller text-based resume.'),
      )
    xhr.onabort = () =>
      reject(new DOMException('Upload cancelled', 'AbortError'))
    const form = new FormData()
    form.append('file', file)
    if (region?.trim()) form.append('phone_region', region.trim().toUpperCase())
    if (signal?.aborted) {
      reject(new DOMException('Upload cancelled', 'AbortError'))
      return
    }
    xhr.send(form)
  })
}
