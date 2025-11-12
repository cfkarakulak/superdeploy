import { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import SecretForm from '../../components/SecretForm'

const API_URL = 'http://localhost:6001'

interface Environment {
  id: number
  name: string
  project_id: number
}

interface Secret {
  id: number
  environment_id: number
  app: string
  key: string
  value: string
}

export default function ProjectSecrets() {
  const router = useRouter()
  const { name: projectName } = router.query
  
  const [project, setProject] = useState<any>(null)
  const [environments, setEnvironments] = useState<Environment[]>([])
  const [currentEnvId, setCurrentEnvId] = useState<number | null>(null)
  const [secrets, setSecrets] = useState<Secret[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingSecret, setEditingSecret] = useState<Secret | null>(null)
  const [revealedSecrets, setRevealedSecrets] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (projectName) {
      fetchProject()
    }
  }, [projectName])

  useEffect(() => {
    if (currentEnvId) {
      fetchSecrets()
    }
  }, [currentEnvId])

  const fetchProject = async () => {
    try {
      const projectsRes = await fetch(`${API_URL}/api/projects`)
      const projectsData = await projectsRes.json()
      const proj = projectsData.find((p: any) => p.name === projectName)
      
      if (proj) {
        setProject(proj)
        
        const envsRes = await fetch(`${API_URL}/api/environments/project/${proj.id}`)
        const envsData = await envsRes.json()
        setEnvironments(envsData)
        
        if (envsData.length > 0) {
          setCurrentEnvId(envsData[0].id)
        }
      }
    } catch (error) {
      console.error('Failed to fetch project:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchSecrets = async () => {
    if (!currentEnvId) return
    
    try {
      const res = await fetch(`${API_URL}/api/secrets/environment/${currentEnvId}`)
      const data = await res.json()
      setSecrets(data)
    } catch (error) {
      console.error('Failed to fetch secrets:', error)
    }
  }

  const handleSaveSecret = async () => {
    setShowAddForm(false)
    setEditingSecret(null)
    await fetchSecrets()
  }

  const handleDeleteSecret = async (secretId: number) => {
    if (!confirm('Are you sure you want to delete this secret?')) return
    
    try {
      await fetch(`${API_URL}/api/secrets/${secretId}`, { method: 'DELETE' })
      await fetchSecrets()
    } catch (error) {
      console.error('Failed to delete secret:', error)
    }
  }

  const toggleReveal = (secretId: number) => {
    const newRevealed = new Set(revealedSecrets)
    if (newRevealed.has(secretId)) {
      newRevealed.delete(secretId)
    } else {
      newRevealed.add(secretId)
    }
    setRevealedSecrets(newRevealed)
  }

  const groupedSecrets = secrets.reduce((acc, secret) => {
    if (!acc[secret.app]) acc[secret.app] = []
    acc[secret.app].push(secret)
    return acc
  }, {} as Record<string, Secret[]>)

  const currentEnv = environments.find(e => e.id === currentEnvId)

  if (loading) {
    return (
      <div className="container">
        <h1 style={{ marginTop: '40px' }}>Loading...</h1>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="container">
        <h1 style={{ marginTop: '40px' }}>Project not found</h1>
      </div>
    )
  }

  return (
    <div className="container">
      <div style={{ marginTop: '40px', marginBottom: '20px' }}>
        <button
          onClick={() => router.push('/')}
          style={{
            background: 'none',
            color: '#0070f3',
            fontSize: '14px',
            marginBottom: '16px',
            textDecoration: 'underline'
          }}
        >
          ← Back to projects
        </button>
        <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>{project.name}</h1>
        <p style={{ color: '#666' }}>Manage secrets for {currentEnv?.name} environment</p>
      </div>

      {/* Environment Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '2px solid #eee' }}>
        {environments.map((env) => (
          <button
            key={env.id}
            onClick={() => setCurrentEnvId(env.id)}
            style={{
              padding: '12px 24px',
              background: 'none',
              color: currentEnvId === env.id ? '#0070f3' : '#666',
              borderBottom: currentEnvId === env.id ? '2px solid #0070f3' : '2px solid transparent',
              marginBottom: '-2px',
              fontSize: '14px',
              fontWeight: currentEnvId === env.id ? 600 : 400
            }}
          >
            {env.name}
          </button>
        ))}
      </div>

      {/* Add Secret Button */}
      <div style={{ marginBottom: '20px' }}>
        <button
          onClick={() => setShowAddForm(true)}
          style={{
            background: '#0070f3',
            color: 'white',
            padding: '10px 20px',
            borderRadius: '6px',
            fontSize: '14px'
          }}
        >
          + Add Secret
        </button>
      </div>

      {/* Add/Edit Secret Form */}
      {(showAddForm || editingSecret) && (
        <SecretForm
          environmentId={currentEnvId!}
          secret={editingSecret}
          onSave={handleSaveSecret}
          onCancel={() => {
            setShowAddForm(false)
            setEditingSecret(null)
          }}
        />
      )}

      {/* Secrets Display */}
      {Object.keys(groupedSecrets).length === 0 ? (
        <div style={{ background: 'white', padding: '40px', borderRadius: '8px', textAlign: 'center' }}>
          <p style={{ color: '#666' }}>No secrets configured for this environment yet.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {Object.entries(groupedSecrets).map(([app, appSecrets]) => (
            <div key={app} style={{ background: 'white', borderRadius: '8px', overflow: 'hidden' }}>
              <div style={{ background: '#f8f8f8', padding: '12px 16px', borderBottom: '1px solid #eee' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600 }}>{app}</h3>
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#fafafa', borderBottom: '1px solid #eee' }}>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '13px', fontWeight: 600, color: '#666' }}>Key</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '13px', fontWeight: 600, color: '#666' }}>Value</th>
                    <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: '13px', fontWeight: 600, color: '#666' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {appSecrets.map((secret) => (
                    <tr key={secret.id} style={{ borderBottom: '1px solid #eee' }}>
                      <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontSize: '13px' }}>{secret.key}</td>
                      <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontSize: '13px' }}>
                        {revealedSecrets.has(secret.id) ? (
                          <span>{secret.value}</span>
                        ) : (
                          <span>{'•'.repeat(20)}</span>
                        )}
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <button
                          onClick={() => toggleReveal(secret.id)}
                          style={{
                            background: 'none',
                            color: '#0070f3',
                            fontSize: '13px',
                            marginRight: '8px'
                          }}
                        >
                          {revealedSecrets.has(secret.id) ? 'Hide' : 'Show'}
                        </button>
                        <button
                          onClick={() => setEditingSecret(secret)}
                          style={{
                            background: 'none',
                            color: '#0070f3',
                            fontSize: '13px',
                            marginRight: '8px'
                          }}
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDeleteSecret(secret.id)}
                          style={{
                            background: 'none',
                            color: '#e00',
                            fontSize: '13px'
                          }}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

