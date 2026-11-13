import type { ReactNode } from 'react'

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-card border border-line bg-surface p-6">
      <h2 className="font-medium">{title}</h2>
      <p className="mt-2 max-w-prose text-muted">{children}</p>
    </div>
  )
}

export function PageTitle({ children }: { children: ReactNode }) {
  return <h1 className="mb-6 font-mono text-2xl font-extrabold tracking-tight">{children}</h1>
}
