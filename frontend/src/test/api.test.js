import { describe, expect, it, vi } from 'vitest'
import {
  MAX_FILE_BYTES,
  request,
  safeUrl,
  scoreLabel,
  uploadResume,
  validateFile,
} from '../lib/api'
describe('file validation and safe display', () => {
  it('validates empty, unsupported, oversized and valid Unicode filenames', () => {
    expect(validateFile(null)).toMatch(/Choose/)
    expect(validateFile({ name: 'cv.exe', size: 1 })).toMatch(/Only PDF/)
    expect(validateFile({ name: 'cv.pdf', size: 0 })).toMatch(/empty/)
    expect(validateFile({ name: 'cv.docx', size: MAX_FILE_BYTES + 1 })).toMatch(
      /smaller/,
    )
    expect(validateFile({ name: 'José 简历.PDF', size: 100 })).toBeNull()
  })
  it('blocks executable and credential-bearing links; preserves null scores', () => {
    expect(safeUrl('javascript:alert(1)')).toBeNull()
    expect(safeUrl('https://user:password@example.com')).toBeNull()
    expect(safeUrl('https://github.com/person')).toBe(
      'https://github.com/person',
    )
    expect(scoreLabel(null)).toBe('Not available')
    expect(scoreLabel(0)).toBe('0.0%')
  })
})
describe('API transport', () => {
  it('sends anonymous requests with no credentials or persistent cache', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ total: 0 }),
    })
    await request('/api/v1/jobs/match')
    expect(fetch.mock.calls[0][0]).not.toContain('private-test-value')
    expect(fetch.mock.calls[0][1]).toMatchObject({
      headers: {},
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
    })
  })
  it('handles secure backend, validation and network errors', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      status: 415,
      ok: false,
      json: async () => ({
        detail: {
          code: 'bad_signature',
          message: 'File signature is invalid.',
        },
      }),
    })
    await expect(request('/upload')).rejects.toMatchObject({
      code: 'bad_signature',
      status: 415,
    })
    fetch.mockResolvedValue({
      status: 422,
      ok: false,
      json: async () => ({ detail: [{ input: 'sensitive' }] }),
    })
    await expect(request('/match')).rejects.toThrow('Please check')
    fetch.mockRejectedValue(new TypeError('Failed fetch'))
    await expect(request('/match')).rejects.toThrow('Cannot reach')
  })
  it('reports upload progress, sends multipart and supports cancellation', async () => {
    let xhr
    class FakeXHR {
      constructor() {
        xhr = this
        this.upload = {}
        this.headers = {}
      }
      open(method, url) {
        this.method = method
        this.url = url
      }
      setRequestHeader(name, value) {
        this.headers[name] = value
      }
      send(body) {
        this.body = body
      }
      abort() {
        this.onabort()
        this.onloadend()
      }
    }
    vi.stubGlobal('XMLHttpRequest', FakeXHR)
    try {
      const control = new AbortController(),
        progress = vi.fn()
      const pending = uploadResume(new File(['text'], 'cv.pdf'), {
        store: false,
        region: 'gb',
        signal: control.signal,
        onProgress: progress,
      })
      xhr.upload.onprogress({ lengthComputable: true, loaded: 2, total: 4 })
      expect(progress).toHaveBeenCalledWith(50)
      xhr.upload.onload()
      expect(progress).toHaveBeenLastCalledWith(100)
      expect(xhr.headers).toEqual({})
      expect(xhr.body.get('phone_region')).toBe('GB')
      expect(xhr.url).toContain('store=false')
      control.abort()
      await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
