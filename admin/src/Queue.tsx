import { useEffect, useState, useCallback } from 'react'
import { type QueueItem, fetchQueue } from './api'
import ReviewModal from './ReviewModal'

interface Props {
  apiKey: string
  onLogout: () => void
}

export default function Queue({ apiKey, onLogout }: Props) {
  const [items, setItems] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<QueueItem | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchQueue(apiKey)
      setItems(data)
    } catch (e: any) {
      if (e.message === 'Invalid API key') onLogout()
      else setError(e.message ?? 'Failed to load queue.')
    } finally {
      setLoading(false)
    }
  }, [apiKey, onLogout])

  useEffect(() => { load() }, [load])

  function handleDone() {
    setSelected(null)
    load()
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Top bar */}
      <div className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div>
          <span className="text-white font-semibold">MuskMaker Admin</span>
          <span className="text-gray-500 text-sm ml-3">Review Queue</span>
        </div>
        <div className="flex items-center gap-4">
          {!loading && (
            <span className="text-gray-400 text-sm">
              {items.length} pending
            </span>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="text-gray-400 hover:text-white text-sm transition-colors disabled:opacity-40"
          >
            ↻ Refresh
          </button>
          <button
            onClick={onLogout}
            className="text-gray-500 hover:text-white text-sm transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {loading && (
          <div className="flex justify-center py-24">
            <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!loading && error && (
          <div className="bg-red-900/30 border border-red-800 rounded-xl p-4 text-red-300 text-sm">
            {error}
          </div>
        )}

        {!loading && !error && items.length === 0 && (
          <div className="text-center py-24 text-gray-500">
            <p className="text-4xl mb-3">✓</p>
            <p className="text-lg font-medium text-gray-400">Queue is empty</p>
            <p className="text-sm mt-1">All verifications have been reviewed.</p>
          </div>
        )}

        {!loading && items.length > 0 && (
          <div className="flex flex-col gap-3">
            {items.map(item => {
              const slaDate = new Date(item.sla_deadline)
              const overSla = slaDate < new Date()
              const queuedDate = new Date(item.queued_at)

              return (
                <div
                  key={item.review_id}
                  className="bg-gray-900 border border-gray-800 hover:border-gray-700 rounded-xl p-5 flex items-center gap-5 cursor-pointer transition-colors"
                  onClick={() => setSelected(item)}
                >
                  {/* Priority badge */}
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-sm font-semibold flex-shrink-0 ${
                    item.priority <= 3 ? 'bg-red-900/50 text-red-300' :
                    item.priority <= 6 ? 'bg-yellow-900/50 text-yellow-300' :
                    'bg-gray-800 text-gray-400'
                  }`}>
                    {item.priority}
                  </div>
./4
                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium truncate">{item.goal_type_name}</p>
                    <p className="text-gray-400 text-sm mt-0.5">{item.goal_local_date}</p>
                  </div>

                  {/* Photo count */}
                  <div className="text-gray-500 text-sm flex-shrink-0">
                    {item.photo_urls.length} photo{item.photo_urls.length !== 1 ? 's' : ''}
                  </div>

                  {/* SLA */}
                  <div className={`text-sm flex-shrink-0 ${overSla ? 'text-red-400' : 'text-gray-500'}`}>
                    {overSla ? '⚠ SLA overdue' : `Queued ${queuedDate.toLocaleDateString()}`}
                  </div>

                  {/* Arrow */}
                  <div className="text-gray-600 flex-shrink-0">→</div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {selected && (
        <ReviewModal
          item={selected}
          apiKey={apiKey}
          onDone={handleDone}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}
