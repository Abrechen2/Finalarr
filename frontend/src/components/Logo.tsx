// Finalarr mark (docs/DESIGN.md): a tally of five — four strokes count the
// episodes, the gold diagonal closes the bundle: counted to the end.
const STROKES = [13, 23, 33, 43] as const

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden="true">
      {STROKES.map((x) => (
        <rect key={x} x={x} y={12} width={7} height={40} rx={3.5} className="fill-ink" />
      ))}
      <line
        x1={8}
        y1={45}
        x2={56}
        y2={19}
        strokeWidth={7}
        strokeLinecap="round"
        className="stroke-gold"
      />
    </svg>
  )
}
