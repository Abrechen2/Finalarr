// Finalarr mark (PLAN.md 16.2): a ring of 12 segments, the last one in the
// accent colour with a square end mark — the finale. Built from geometry.
const SEGMENTS = 12
const CENTER = 32
const RADIUS = 25
const GAP_DEG = 7

function point(deg: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180
  return [CENTER + RADIUS * Math.cos(rad), CENTER + RADIUS * Math.sin(rad)]
}

function arc(index: number): string {
  const step = 360 / SEGMENTS
  const [x1, y1] = point(index * step + GAP_DEG / 2)
  const [x2, y2] = point((index + 1) * step - GAP_DEG / 2)
  return `M${x1.toFixed(2)} ${y1.toFixed(2)}A${RADIUS} ${RADIUS} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`
}

export function Logo({ size = 32, withLetter = true }: { size?: number; withLetter?: boolean }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden="true">
      {Array.from({ length: SEGMENTS }, (_, i) => (
        <path
          key={i}
          d={arc(i)}
          fill="none"
          strokeWidth={6}
          className={i === SEGMENTS - 1 ? 'stroke-accent' : 'stroke-ink'}
        />
      ))}
      <rect x={29} y={3} width={6} height={6} className="fill-accent" />
      {withLetter && (
        <text
          x={32}
          y={41}
          textAnchor="middle"
          className="fill-ink font-mono"
          fontSize={24}
          fontWeight={800}
        >
          F
        </text>
      )}
    </svg>
  )
}
