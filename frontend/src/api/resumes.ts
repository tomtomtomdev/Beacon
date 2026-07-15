import type { Resume, ResumeCreate } from './types'

// GET /resumes — every stored resume, active flag included.
export async function fetchResumes(): Promise<Resume[]> {
  const response = await fetch('/resumes')
  if (!response.ok) {
    throw new Error(`GET /resumes failed: ${response.status}`)
  }
  return (await response.json()) as Resume[]
}

// POST /resumes — paste/.txt text; the API parses → profiles → stores (and sets active).
export async function createResume(body: ResumeCreate): Promise<Resume> {
  const response = await fetch('/resumes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(`POST /resumes failed: ${response.status}`)
  }
  return (await response.json()) as Resume
}

// PUT /resumes/{id}/active — make this the resume that scores the job list.
export async function activateResume(id: number): Promise<Resume> {
  const response = await fetch(`/resumes/${id}/active`, { method: 'PUT' })
  if (!response.ok) {
    throw new Error(`PUT /resumes/${id}/active failed: ${response.status}`)
  }
  return (await response.json()) as Resume
}

export async function deleteResume(id: number): Promise<void> {
  const response = await fetch(`/resumes/${id}`, { method: 'DELETE' })
  if (!response.ok) {
    throw new Error(`DELETE /resumes/${id} failed: ${response.status}`)
  }
}
