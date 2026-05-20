import { useState } from 'react'
import { type QueueItem, claimReview, decideReview } from './api'

interface Props {
  item: QueueItem
  apiKey: string
  onDone: () => void
  onClose: () => void
}

export default function ReviewModal({ item, apiKey, onDone, onClose }: Props) {
  const [photoIndex, setPhotoIndex] = useState(0)
  const [rejectionReason, setRejectionReason] = useState('')
  const [reviewerNotes, setReviewerNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const slaDate = new Date(item.sla_deadline)
  const overSla = slaDate < new Date()

  async function decide(decision: 'approved' | 'rejected') {
    if (decision === 'rejected' && !rejectionReason.trim()) {
      setError('Rejection reason is required.')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      await claimReview(apiKey, item.review_id)
      await decideReview(apiKey, item.review_id, decision, rejectionReason || undefined, reviewerNotes || undefined)
      onDone()
    } catch (e: any) {
      setError(e.message ?? 'Something went wrong.')
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl">

        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-gray-800">
          <div>
            <h2 className="text-white text-lg font-semibold">{item.goal_type_name}</h2>
            <p className="text-gray-400 text-sm mt-0.5">{item.goal_local_date}</p>
            <div className="flex gap-2 mt-2">
              <span className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded-full">
                Priority {item.priority}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${overSla ? 'bg-red-900/50 text-red-300' : 'bg-gray-800 text-gray-300'}`}>
                SLA {overSla ? 'overdue' : slaDate.toLocaleString()}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors text-xl leading-none">✕</button>
        </div>

        {/* Photos */}
        <div className="p-6 border-b border-gray-800">
          {item.photo_urls.length === 0 ? (
            <p className="text-gray-500 text-sm">No photos attached.</p>
          ) : (
            <div className="flex flex-col gap-3">
              <img
                src={item.photo_urls[photoIndex]}
                alt={`Photo ${photoIndex + 1}`}
                className="rounded-xl w-full object-contain max-h-96 bg-gray-950"
              />
              {item.photo_urls.length > 1 && (
                <div className="flex gap-2 justify-center">
                  {item.photo_urls.map((url, i) => (
                    <button
                      key={url}
                      onClick={() => setPhotoIndex(i)}
                      className={`w-2 h-2 rounded-full transition-colors ${i === photoIndex ? 'bg-indigo-400' : 'bg-gray-600 hover:bg-gray-400'}`}
                    />
                  ))}
                </div>
              )}
              {item.photo_urls.length > 1 && (
                <div className="flex gap-2">
                  {item.photo_urls.map((url, i) => (
                    <img
                      key={url}
                      src={url}
                      alt={`Thumb ${i + 1}`}
                      onClick={() => setPhotoIndex(i)}
                      className={`w-16 h-16 rounded-lg object-cover cursor-pointer border-2 transition-colors ${i === photoIndex ? 'border-indigo-400' : 'border-transparent opacity-60 hover:opacity-100'}`}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Decision form */}
        <div className="p-6 flex flex-col gap-4">
          <div>
            <label className="text-gray-400 text-sm block mb-1.5">
              Rejection reason <span className="text-gray-600">(required if rejecting)</span>
            </label>
            <input
              type="text"
              value={rejectionReason}
              onChange={e => setRejectionReason(e.target.value)}
              placeholder="e.g. Photo does not show gym equipment"
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="text-gray-400 text-sm block mb-1.5">Reviewer notes <span className="text-gray-600">(internal, optional)</span></label>
            <textarea
              value={reviewerNotes}
              onChange={e => setReviewerNotes(e.target.value)}
              rows={2}
              placeholder="Internal notes..."
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <div className="flex gap-3">
            <button
              onClick={() => decide('approved')}
              disabled={submitting}
              className="flex-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors"
            >
              {submitting ? 'Saving…' : '✓ Approve'}
            </button>
            <button
              onClick={() => decide('rejected')}
              disabled={submitting}
              className="flex-1 bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors"
            >
              {submitting ? 'Saving…' : '✕ Reject'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
