import { useState, useEffect } from 'react'

const API_URL = 'http://localhost:6001'

interface Secret {
  id: number
  environment_id: number
  app: string
  key: string
  value: string
}

interface SecretFormProps {
  environmentId: number
  secret?: Secret | null
  onSave: () => void
  onCancel: () => void
}

export default function SecretForm({ environmentId, secret, onSave, onCancel }: SecretFormProps) {
  const [app, setApp] = useState(secret?.app || 'shared')
  const [key, setKey] = useState(secret?.key || '')
  const [value, setValue] = useState(secret?.value || '')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (secret) {
      setApp(secret.app)
      setKey(secret.key)
      setValue(secret.value)
    }
  }, [secret])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    if (!key.trim() || !value.trim()) {
      setError('Key and value are required')
      return
    }

    setSubmitting(true)

    try {
      if (secret) {
        // Update existing secret
        await fetch(`${API_URL}/api/secrets/${secret.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value })
        })
      } else {
        // Create new secret
        await fetch(`${API_URL}/api/secrets`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            environment_id: environmentId,
            app,
            key,
            value
          })
        })
      }
      onSave()
    } catch (err) {
      setError('Failed to save secret')
      console.error(err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        background: 'white',
        padding: '24px',
        borderRadius: '8px',
        marginBottom: '24px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
      }}
    >
      <h3 style={{ fontSize: '18px', marginBottom: '20px', fontWeight: 600 }}>
        {secret ? 'Edit Secret' : 'Add New Secret'}
      </h3>

      {error && (
        <div style={{
          background: '#fee',
          color: '#c00',
          padding: '12px',
          borderRadius: '4px',
          marginBottom: '16px',
          fontSize: '14px'
        }}>
          {error}
        </div>
      )}

      <div style={{ marginBottom: '16px' }}>
        <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', fontWeight: 500 }}>
          App
        </label>
        <select
          value={app}
          onChange={(e) => setApp(e.target.value)}
          disabled={!!secret}
          style={{
            width: '100%',
            padding: '10px 12px',
            border: '1px solid #ddd',
            borderRadius: '6px',
            fontSize: '14px',
            background: secret ? '#f5f5f5' : 'white'
          }}
        >
          <option value="shared">Shared</option>
          <option value="api">API</option>
          <option value="services">Services</option>
          <option value="storefront">Storefront</option>
        </select>
      </div>

      <div style={{ marginBottom: '16px' }}>
        <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', fontWeight: 500 }}>
          Key
        </label>
        <input
          type="text"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          disabled={!!secret}
          placeholder="e.g., X_API_KEY"
          style={{
            width: '100%',
            padding: '10px 12px',
            border: '1px solid #ddd',
            borderRadius: '6px',
            fontSize: '14px',
            fontFamily: 'monospace',
            background: secret ? '#f5f5f5' : 'white'
          }}
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', fontWeight: 500 }}>
          Value
        </label>
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Enter the secret value..."
          rows={4}
          style={{
            width: '100%',
            padding: '10px 12px',
            border: '1px solid #ddd',
            borderRadius: '6px',
            fontSize: '14px',
            fontFamily: 'monospace',
            resize: 'vertical'
          }}
        />
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        <button
          type="submit"
          disabled={submitting}
          style={{
            background: '#0070f3',
            color: 'white',
            padding: '10px 24px',
            borderRadius: '6px',
            fontSize: '14px',
            fontWeight: 500,
            opacity: submitting ? 0.7 : 1
          }}
        >
          {submitting ? 'Saving...' : secret ? 'Update' : 'Save'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          style={{
            background: '#f5f5f5',
            color: '#333',
            padding: '10px 24px',
            borderRadius: '6px',
            fontSize: '14px'
          }}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

