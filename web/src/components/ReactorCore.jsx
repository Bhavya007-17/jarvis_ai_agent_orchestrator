// Signature element: an Iron-Man "arc reactor" core — concentric rotating
// rings around a pulsing center. Pure SVG/CSS (no canvas), animated via the
// Tailwind keyframes defined in tailwind.config.js. Honors reduced-motion
// through the global media query in index.css.
export default function ReactorCore({ size = 56, active = false }) {
  const stroke = active ? 'rgba(34,211,238,0.95)' : 'rgba(34,211,238,0.55)'
  return (
    <div className="relative" style={{ width: size, height: size }} aria-hidden="true">
      {/* outer ticked ring — rotates slowly */}
      <svg viewBox="0 0 100 100" className="absolute inset-0 animate-spin-slow"
        style={{ filter: 'drop-shadow(0 0 6px rgba(34,211,238,0.5))' }}>
        <circle cx="50" cy="50" r="46" fill="none" stroke={stroke} strokeWidth="1.5"
          strokeDasharray="3 6" opacity="0.7" />
      </svg>
      {/* mid ring — counter-rotates */}
      <svg viewBox="0 0 100 100" className="absolute inset-0 animate-spin-rev">
        <circle cx="50" cy="50" r="34" fill="none" stroke="rgba(34,211,238,0.7)" strokeWidth="2"
          strokeDasharray="40 14" strokeLinecap="round" />
      </svg>
      {/* segmented inner ring (static frame) */}
      <svg viewBox="0 0 100 100" className="absolute inset-0">
        {Array.from({ length: 8 }).map((_, i) => (
          <line key={i} x1="50" y1="50" x2="50" y2="28"
            stroke="rgba(34,211,238,0.45)" strokeWidth="2"
            transform={`rotate(${i * 45} 50 50)`} />
        ))}
        <circle cx="50" cy="50" r="22" fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="1.5" />
      </svg>
      {/* glowing pulsing core */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="rounded-full animate-core-pulse"
          style={{
            width: size * 0.3, height: size * 0.3,
            background: 'radial-gradient(circle, #E0FBFF 0%, #22D3EE 45%, #0E7490 100%)',
            boxShadow: '0 0 18px 4px rgba(34,211,238,0.7)',
          }} />
      </div>
    </div>
  )
}
