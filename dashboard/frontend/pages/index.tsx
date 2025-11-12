import { useState, useEffect } from 'react'
import { useRouter } from 'next/router'

const API_URL = 'http://localhost:6001'

interface Project {
  id: number
  name: string
}

export default function Home() {
  const router = useRouter()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')

  useEffect(() => {
    fetchProjects()
  }, [])

  const fetchProjects = async () => {
    try {
      const res = await fetch(`${API_URL}/api/projects`)
      const data = await res.json()
      setProjects(data)
    } catch (error) {
      console.error('Failed to fetch projects:', error)
    } finally {
      setLoading(false)
    }
  }

  const createProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newProjectName.trim()) return

    try {
      await fetch(`${API_URL}/api/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newProjectName })
      })
      setNewProjectName('')
      setShowCreateForm(false)
      fetchProjects()
    } catch (error) {
      console.error('Failed to create project:', error)
    }
  }

  if (loading) {
    return (
      <div className="container">
        <h1 style={{ marginTop: '40px' }}>Loading...</h1>
      </div>
    )
  }

  return (
    <div className="container">
      <div style={{ marginTop: '40px', marginBottom: '40px' }}>
        <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>SuperDeploy Dashboard</h1>
        <p style={{ color: '#666' }}>Manage secrets across environments</p>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          style={{
            background: '#0070f3',
            color: 'white',
            padding: '10px 20px',
            borderRadius: '6px',
            fontSize: '14px'
          }}
        >
          {showCreateForm ? 'Cancel' : '+ New Project'}
        </button>
      </div>

      {showCreateForm && (
        <form
          onSubmit={createProject}
          style={{
            background: 'white',
            padding: '20px',
            borderRadius: '8px',
            marginBottom: '20px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}
        >
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontWeight: 500 }}>
              Project Name
            </label>
            <input
              type="text"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              placeholder="e.g., cheapa"
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                fontSize: '14px'
              }}
            />
          </div>
          <button
            type="submit"
            style={{
              background: '#0070f3',
              color: 'white',
              padding: '8px 16px',
              borderRadius: '4px',
              fontSize: '14px'
            }}
          >
            Create Project
          </button>
        </form>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '16px' }}>
        {projects.length === 0 ? (
          <p style={{ color: '#666', gridColumn: '1 / -1' }}>No projects yet. Create one to get started.</p>
        ) : (
          projects.map((project) => (
            <div
              key={project.id}
              onClick={() => router.push(`/project/${project.name}`)}
              style={{
                background: 'white',
                padding: '24px',
                borderRadius: '8px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                cursor: 'pointer',
                transition: 'transform 0.2s, box-shadow 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)'
                e.currentTarget.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)'
              }}
            >
              <h3 style={{ fontSize: '18px', marginBottom: '8px' }}>{project.name}</h3>
              <p style={{ color: '#666', fontSize: '14px' }}>Click to manage secrets</p>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

