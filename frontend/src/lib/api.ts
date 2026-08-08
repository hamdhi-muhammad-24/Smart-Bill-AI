export const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8090').replace(/\/+$/, '')

const TOKEN_KEY = 'slt-token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  const authHeader: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {}

  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeader,
      ...(init?.headers ?? {}),
    },
  })

  if (res.status === 401) {
    clearToken()
    localStorage.removeItem('slt-auth')
    window.location.href = '/login'
    throw new ApiError(401, 'Session expired - please log in again.')
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail: string }
      if (body.detail) detail = body.detail
    } catch {
      // ignore JSON parse failure; use statusText
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

// --- Auth endpoints ---

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface MeResponse {
  id: number
  email: string
  role: 'ADMIN' | 'GMF_HANDLER' | 'MANAGER' | 'CUSTOMER' | 'ADMIN1'
  customer_id: number | null
}


export function authMe(): Promise<MeResponse> {
  return request('/auth/me')
}

// --- User Management Endpoints ---

export interface UserOut {
  id: number
  email: string
  role: 'ADMIN' | 'GMF_HANDLER' | 'MANAGER' | 'CUSTOMER'
  is_active: boolean
  created_at?: string
}

export function getUsers(): Promise<UserOut[]> {
  return request('/users')
}

export function createUser(data: { email: string; role: string; is_active?: boolean }): Promise<UserOut> {
  return request('/users', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function deleteUser(id: number): Promise<void> {
  return request(`/users/${id}`, {
    method: 'DELETE',
  })
}

// --- Billing / GMF Endpoints ---

export interface DashboardStats {
  gmfs_received_today: number
  gmfs_pending_review: number
  total_invoices_generated: number
  total_invoices_failed: number
  success_rate: number
  active_runs: number
  active_schedules: number
  unread_notifications: number
  cycles: Record<string, { received: number; status: string }>
}

export interface GmfUploadOut {
  id: number
  filename: string
  file_path: string
  folder_type: string
  cycle_number: number | null
  template_detected: string | null
  status: string
  detected_at: string
  processed_at: string | null
  error_message: string | null
  rejection_reason: string | null
  billing_run_id: number | null
  template_status?: string | null
  processed_records_count?: number
  total_records_count?: number
  template_breakdown?: Record<string, number> | null
}

export interface TemplateBreakdownItem {
  template_id: string
  template_name: string
  count: number
  is_approved: boolean
  status: string
}

export interface GmfSummaryOut {
  upload_id: number
  filename: string
  is_red_notice: boolean
  folder_type: string
  status: string
  total_documents: number
  processed_documents: number
  remaining_documents: number
  template_detected: string | null
  detected_at: string
  template_breakdown: TemplateBreakdownItem[]
}

export function getUploadSummary(uploadId: number): Promise<GmfSummaryOut> {
  return request(`/billing/uploads/${uploadId}/summary`)
}


export interface BillingRunOut {
  id: number
  batch_name: string
  cycle_number: number | null
  status: string
  total_accounts: number
  succeeded: number
  failed: number
  started_at: string
  finished_at: string | null
  output_path: string | null
}

export interface ScheduleOut {
  id: number
  name: string
  day_of_month: number
  run_time: string
  timezone: string
  schedule_mode: string
  is_active: boolean
  approval_lead_days: number
  created_at: string
}

export interface NotificationOut {
  id: number
  event_type: string
  title: string
  message: string
  upload_id: number | null
  run_id: number | null
  is_read: boolean
  created_at: string
}

export function getStats(): Promise<DashboardStats> {
  return request('/billing/stats')
}

export function getUploads(status?: string, cycle?: number): Promise<GmfUploadOut[]> {
  const params = new URLSearchParams()
  if (status) params.append('status', status)
  if (cycle) params.append('cycle', cycle.toString())
  const q = params.toString() ? `?${params.toString()}` : ''
  return request(`/billing/uploads${q}`)
}

export interface PreviewInvoiceResponse {
  message: string
  pdf_url: string
  template_detected: string
}

export function previewInvoice(uploadId: number, signal?: AbortSignal): Promise<PreviewInvoiceResponse> {
  return request(`/billing/preview/${uploadId}`, { method: 'POST', signal })
}

export async function fetchPreviewPdfBlobUrl(pdfUrl: string, signal?: AbortSignal): Promise<string> {
  const token = getToken()
  const url = pdfUrl.startsWith('http') ? pdfUrl : `${BASE_URL}${pdfUrl}`
  const response = await fetch(url, {
    signal,
    headers: {
      Authorization: `Bearer ${token}`
    }
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const json = await response.json() as { detail: string }
      if (json.detail) detail = json.detail
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail)
  }

  const blob = await response.blob()
  return URL.createObjectURL(blob)
}

export function approveUpload(uploadId: number): Promise<{ message: string; upload_id: number }> {
  return request(`/billing/approve/${uploadId}`, { method: 'POST' })
}

export function rejectUpload(uploadId: number, reason: string): Promise<{ message: string; upload_id: number }> {
  return request(`/billing/reject/${uploadId}`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

export function generateBatch(uploadId: number): Promise<{ message: string; run_id: number }> {
  return request(`/billing/generate/${uploadId}`, { method: 'POST' })
}

export interface PendingBatchOut {
  cycle_number: number | string
  date: string
  batch_index: number
  file_count: number
  upload_ids: number[]
  processed_records?: number
  total_records?: number
  remaining_records?: number
}

export function getPendingBatches(): Promise<PendingBatchOut[]> {
  return request('/billing/pending-batches')
}

export function generateGroupBatch(uploadIds: number[], recordLimit?: number | null): Promise<{ message: string; run_id: number }> {
  return request(`/billing/generate-batch`, {
    method: 'POST',
    body: JSON.stringify({ upload_ids: uploadIds, limit: recordLimit }),
  })
}

export function retryFailedRun(runId: number): Promise<{ message: string }> {
  return request(`/billing/runs/${runId}/retry`, {
    method: 'POST'
  })
}

export function getRuns(): Promise<BillingRunOut[]> {
  return request('/billing/runs')
}

export function getRun(runId: number): Promise<BillingRunOut> {
  return request(`/billing/runs/${runId}`)
}

export interface RunResultSuccess {
  date: string
  cycle: string
  batch: string
  filename: string
  account_number: string
}

export interface RunResultFailure {
  account_number: string
  error_message: string
}

export interface GmfUploadDetail {
  id: number
  filename: string
  folder_type: string
  status: string
  error_message: string | null
}

export interface RunResultsOut {
  run_id: number
  successes: RunResultSuccess[]
  failures: RunResultFailure[]
  gmf_successes: GmfUploadDetail[]
  gmf_failures: GmfUploadDetail[]
  gmf_running: GmfUploadDetail[]
}

export function getRunResults(runId: number): Promise<RunResultsOut> {
  return request(`/billing/runs/${runId}/results`)
}

export function getOutputDates(): Promise<{ dates: string[] }> {
  return request('/billing/output/dates')
}

export function getOutputCycles(dateStr: string): Promise<{ date: string; cycles: string[] }> {
  return request(`/billing/output/${dateStr}`)
}

export function getOutputBatches(dateStr: string, cycle: string): Promise<{ date: string; cycle: string; batches: { batch: string; pdf_count: number }[] }> {
  return request(`/billing/output/${dateStr}/${cycle}`)
}

export function getOutputPdfs(dateStr: string, cycle: string, batch: string): Promise<{ date: string; cycle: string; batch: string; files: string[] }> {
  return request(`/billing/output/${dateStr}/${cycle}/${batch}`)
}

// Fetch PDF securely as a Blob and create an Object URL
export async function fetchPdfBlobUrl(dateStr: string, cycle: string, batch: string, filename: string): Promise<string> {
  const token = getToken()
  const response = await fetch(`${BASE_URL}/billing/output/${dateStr}/${cycle}/${batch}/${filename}`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  })
  
  if (!response.ok) {
    throw new Error('Failed to fetch PDF')
  }
  
  const blob = await response.blob()
  return URL.createObjectURL(blob)
}

export function getTemplates(): Promise<{ templates: any[] }> {
  return request('/billing/templates')
}

export function updateTemplateStatus(templateId: string, status: string, reason?: string): Promise<{ message: string; status: string }> {
  return request(`/billing/templates/${templateId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status, reason })
  })
}

export async function fetchTemplatePreviewBlobUrl(templateId: string): Promise<string> {
  const token = getToken()
  const response = await fetch(`${BASE_URL}/billing/templates/${templateId}/preview`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  })
  
  if (!response.ok) {
    throw new Error('Failed to fetch template preview')
  }
  
  const blob = await response.blob()
  return URL.createObjectURL(blob)
}

export function getNotifications(unreadOnly = false): Promise<NotificationOut[]> {
  const q = unreadOnly ? '?unread_only=true' : ''
  return request(`/billing/notifications${q}`)
}

export function markNotificationRead(notifId: number): Promise<{ ok: boolean }> {
  return request(`/billing/notifications/${notifId}/read`, { method: 'PATCH' })
}

export function markAllNotificationsRead(): Promise<{ ok: boolean }> {
  return request('/billing/notifications/mark-all-read', { method: 'PATCH' })
}

export function clearReadNotifications(): Promise<{ ok: boolean }> {
  return request('/billing/notifications/clear-read', { method: 'DELETE' })
}

export function getSchedules(): Promise<ScheduleOut[]> {
  return request('/billing/schedules')
}

export function createSchedule(data: any): Promise<ScheduleOut> {
  return request('/billing/schedules', { method: 'POST', body: JSON.stringify(data) })
}

export function updateSchedule(id: number, data: any): Promise<ScheduleOut> {
  return request(`/billing/schedules/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function toggleSchedule(id: number): Promise<{ id: number; is_active: boolean }> {
  return request(`/billing/schedules/${id}/toggle`, { method: 'PATCH' })
}

export function deleteSchedule(id: number): Promise<{ ok: boolean }> {
  return request(`/billing/schedules/${id}`, { method: 'DELETE' })
}

export function getSettings(): Promise<{ billing_mode: string }> {
  return request('/billing/settings')
}

export function updateSettings(data: { billing_mode: string }): Promise<{ billing_mode: string }> {
  return request('/billing/settings', { method: 'PATCH', body: JSON.stringify(data) })
}

export function getTemplateHistory(): Promise<any[]> {
  return request('/billing/template-history')
}

export function deleteTemplateHistoryLog(historyId: number): Promise<{ message: string }> {
  return request(`/billing/template-history/${historyId}`, { method: 'DELETE' })
}

export function deleteAllTemplateHistoryLogs(): Promise<{ message: string }> {
  return request('/billing/template-history', { method: 'DELETE' })
}

export function getEnvelopeHistory(): Promise<any[]> {
  return request('/api/envelope/history')
}

export function deleteEnvelopeHistoryLog(historyId: number): Promise<{ message: string }> {
  return request(`/api/envelope/history/${historyId}`, { method: 'DELETE' })
}

export function deleteAllEnvelopeHistoryLogs(): Promise<{ message: string }> {
  return request('/api/envelope/history', { method: 'DELETE' })
}

export function deleteRun(runId: number): Promise<{ message: string }> {
  return request(`/billing/runs/${runId}`, { method: 'DELETE' })
}

export function deleteAllRuns(): Promise<{ message: string }> {
  return request('/billing/runs', { method: 'DELETE' })
}

export function scanDrive(): Promise<{ message: string }> {
  return request('/billing/scan-drive', { method: 'POST' })
}

export async function uploadGmf(files: File[], folderType: string): Promise<{ message: string }> {
  const token = getToken()
  const formData = new FormData()
  formData.append('folder_type', folderType)
  files.forEach((file) => {
    formData.append('files', file)
  })
  
  const res = await fetch(`${BASE_URL}/billing/upload-gmf`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: formData
  })
  
  if (!res.ok) {
    let detail = res.statusText
    try {
      const json = await res.json() as { detail: string }
      if (json.detail) detail = json.detail
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<{ message: string }>
}

export function deleteUpload(uploadId: number): Promise<{ message: string }> {
  return request(`/billing/uploads/${uploadId}`, { method: 'DELETE' })
}

export function clearAllUploads(folderType?: string): Promise<{ message: string; deleted_count: number; skipped_count: number }> {
  const q = folderType ? `?folder_type=${folderType}` : ''
  return request(`/billing/uploads${q}`, { method: 'DELETE' })
}
