import { uploadGmf } from './api'

export type UploadJobStatus = 'uploading' | 'completed' | 'failed'

export interface UploadJob {
  id: string
  folderType: string
  fileCount: number
  uploadedCount: number
  failedCount: number
  status: UploadJobStatus
  startedAt: string
  finishedAt: string | null
  message: string | null
}

const STORAGE_KEY = 'slt-upload-jobs'
const CHUNK_SIZE = 50
const CONCURRENCY = 6

const listeners = new Set<() => void>()

let jobs: UploadJob[] = loadJobs()

function loadJobs(): UploadJob[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const storedJobs = raw ? JSON.parse(raw) as UploadJob[] : []
    return storedJobs.map(job => job.status === 'uploading'
      ? {
          ...job,
          status: 'failed',
          finishedAt: new Date().toISOString(),
          message: 'Upload was interrupted by a browser refresh.',
        }
      : job
    )
  } catch {
    return []
  }
}

function persistJobs() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs.slice(0, 25)))
}

function emit() {
  persistJobs()
  listeners.forEach(listener => listener())
}

function patchJob(id: string, patch: Partial<UploadJob>) {
  jobs = jobs.map(job => job.id === id ? { ...job, ...patch } : job)
  emit()
}

export function subscribeUploadJobs(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function getUploadJobsSnapshot(): UploadJob[] {
  return jobs
}

export function clearCompletedUploadJobs() {
  jobs = jobs.filter(job => job.status === 'uploading')
  emit()
}

export function hasActiveUploadJobs(): boolean {
  return jobs.some(job => job.status === 'uploading')
}

export function startUploadJob(files: File[], folderType: string): { id: string; done: Promise<UploadJob> } {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`
  const job: UploadJob = {
    id,
    folderType,
    fileCount: files.length,
    uploadedCount: 0,
    failedCount: 0,
    status: 'uploading',
    startedAt: new Date().toISOString(),
    finishedAt: null,
    message: null,
  }

  jobs = [job, ...jobs].slice(0, 25)
  emit()

  const chunks: File[][] = []
  for (let i = 0; i < files.length; i += CHUNK_SIZE) {
    chunks.push(files.slice(i, i + CHUNK_SIZE))
  }

  const done = runUploadChunks(id, chunks, folderType)
  return { id, done }
}

async function runUploadChunks(id: string, chunks: File[][], folderType: string): Promise<UploadJob> {
  let nextIndex = 0
  let uploadedCount = 0
  let failedCount = 0
  let firstError: string | null = null

  async function worker() {
    while (nextIndex < chunks.length) {
      const chunk = chunks[nextIndex]
      nextIndex += 1

      try {
        await uploadGmf(chunk, folderType)
        uploadedCount += chunk.length
      } catch (err) {
        failedCount += chunk.length
        if (!firstError) {
          firstError = err instanceof Error ? err.message : 'Upload failed'
        }
      }

      patchJob(id, { uploadedCount, failedCount })
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, chunks.length) }, () => worker())
  )

  const status: UploadJobStatus = failedCount > 0 ? 'failed' : 'completed'
  const message = firstError ?? `Uploaded ${uploadedCount} file(s).`
  const finishedAt = new Date().toISOString()
  patchJob(id, { uploadedCount, failedCount, status, finishedAt, message })

  return jobs.find(job => job.id === id)!
}
