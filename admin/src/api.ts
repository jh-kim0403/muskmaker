const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface QueueItem {
  review_id: string
  verification_id: string
  user_id: string
  goal_type_name: string
  goal_local_date: string
  queued_at: string
  sla_deadline: string
  priority: number
  photo_urls: string[]
}

export interface DecisionResponse {
  review_id: string
  verification_id: string
  decision: string
  coins_awarded: number
}

function headers(apiKey: string) {
  return {
    'Content-Type': 'application/json',
    'X-Admin-Key': apiKey,
  }
}

export async function fetchQueue(apiKey: string): Promise<QueueItem[]> {
  const res = await fetch(`${API_BASE}/api/v1/admin/reviews/queue`, {
    headers: headers(apiKey),
  })
  if (res.status === 403) throw new Error('Invalid API key')
  if (!res.ok) throw new Error(`Server error: ${res.status}`)
  return res.json()
}

export async function claimReview(apiKey: string, reviewId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/admin/reviews/${reviewId}/claim`, {
    method: 'POST',
    headers: headers(apiKey),
  })
  if (!res.ok && res.status !== 404) throw new Error(`Claim failed: ${res.status}`)
}

export async function decideReview(
  apiKey: string,
  reviewId: string,
  decision: 'approved' | 'rejected',
  rejectionReason?: string,
  reviewerNotes?: string,
): Promise<DecisionResponse> {
  const res = await fetch(`${API_BASE}/api/v1/admin/reviews/${reviewId}/decide`, {
    method: 'POST',
    headers: headers(apiKey),
    body: JSON.stringify({
      decision,
      rejection_reason: rejectionReason ?? null,
      reviewer_notes: reviewerNotes ?? null,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Decision failed: ${res.status}`)
  }
  return res.json()
}
