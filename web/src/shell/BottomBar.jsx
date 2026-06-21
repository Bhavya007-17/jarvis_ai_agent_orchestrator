import { MODULES } from './modules'

// Fixed bottom feature bar. One button per module; active-glow when open.
// Button accessible name = module label (drives the Playwright gate).
export default function BottomBar({ isOpen, onToggle }) {
  return (
    <nav className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-1 px-2 py-2 glass rounded-2xl shadow-glow">
      {MODULES.map(({ id, label, icon: Icon }) => {
        const on = isOpen(id)
        return (
          <button
            key={id}
            aria-label={label}
            title={label}
            onClick={() => onToggle(id)}
            className={`relative flex flex-col items-center gap-1 px-3 py-1.5 rounded-xl text-[10px] font-medium tracking-wide transition-colors ${
              on ? 'text-core bg-core/10 border border-core/40 shadow-glow-sm' : 'text-[#7FA3B2] hover:text-core/90 border border-transparent'
            }`}
          >
            <Icon size={18} />
            <span>{label}</span>
          </button>
        )
      })}
    </nav>
  )
}
