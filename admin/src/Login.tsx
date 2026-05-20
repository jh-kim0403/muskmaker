interface Props {
  onLogin: (apiKey: string) => void
  error?: string
}

export default function Login({ onLogin, error }: Props) {
  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const key = (e.currentTarget.elements.namedItem('apiKey') as HTMLInputElement).value.trim()
    if (key) onLogin(key)
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 w-full max-w-sm shadow-xl">
        <h1 className="text-white text-2xl font-semibold mb-1">MuskMaker Admin</h1>
        <p className="text-gray-400 text-sm mb-6">Enter your API key to continue</p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            name="apiKey"
            type="password"
            placeholder="API key"
            autoFocus
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />

          {error && (
            <p className="text-red-400 text-sm">{error}</p>
          )}

          <button
            type="submit"
            className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors"
          >
            Sign in
          </button>
        </form>
      </div>
    </div>
  )
}
