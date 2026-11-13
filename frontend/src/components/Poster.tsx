import { Tv } from 'lucide-react'

export function Poster({ url, size = 'sm' }: { url: string | null; size?: 'sm' | 'lg' }) {
  const box = size === 'sm' ? 'h-16 w-11' : 'h-48 w-32'
  if (!url) {
    return (
      <div
        className={`${box} flex shrink-0 items-center justify-center rounded-card border border-line text-muted`}
      >
        <Tv size={size === 'sm' ? 16 : 32} aria-hidden="true" />
      </div>
    )
  }
  return (
    <img
      src={url}
      alt=""
      loading="lazy"
      referrerPolicy="no-referrer"
      className={`${box} shrink-0 rounded-card border border-line object-cover`}
    />
  )
}
