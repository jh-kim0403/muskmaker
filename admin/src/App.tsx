import { useState } from 'react'
import Login from './Login'
import Queue from './Queue'

const STORAGE_KEY = 'mm_admin_key'

export default function App() {
  const [apiKey, setApiKey] = useState<string>(() => localStorage.getItem(STORAGE_KEY) ?? '')

  function handleLogin(key: string) {
    localStorage.setItem(STORAGE_KEY, key)
    setApiKey(key)
  }

  function handleLogout() {
    localStorage.removeItem(STORAGE_KEY)
    setApiKey('')
  }

  if (!apiKey) {
    return <Login onLogin={handleLogin} />
  }

  return <Queue apiKey={apiKey} onLogout={handleLogout} />
}
