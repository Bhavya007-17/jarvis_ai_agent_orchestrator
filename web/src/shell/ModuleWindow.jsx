import { useCallback, useRef } from 'react'
import { X } from 'lucide-react'

// Center-anchored draggable window. Drag math ported from ada's
// handleMouseDown/Drag/Up: offset = pointer - elementCenter; new center =
// pointer - offset. Refs avoid closure-staleness in the move listener.
export default function ModuleWindow({ id, title, icon: Icon, x, y, z, w, h, onFocus, onMove, onClose, children }) {
  const offset = useRef({ x: 0, y: 0 })
  const dragging = useRef(false)

  const onPointerMove = useCallback((e) => {
    if (!dragging.current) return
    onMove(id, e.clientX - offset.current.x, e.clientY - offset.current.y)
  }, [id, onMove])

  const onPointerUp = useCallback(() => {
    dragging.current = false
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', onPointerUp)
  }, [onPointerMove])

  const onHeaderPointerDown = useCallback((e) => {
    // Don't start a drag from the close button or any interactive child.
    if (e.target.closest('button')) return
    offset.current = { x: e.clientX - x, y: e.clientY - y }
    dragging.current = true
    onFocus(id)
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
  }, [id, x, y, onFocus, onPointerMove, onPointerUp])

  return (
    <div
      data-window-id={id}
      onMouseDown={() => onFocus(id)}
      className="absolute glass rounded-xl shadow-glow flex flex-col overflow-hidden"
      style={{ left: x, top: y, width: w, height: h, zIndex: z, transform: 'translate(-50%, -50%)' }}
    >
      <header
        data-drag-handle
        onPointerDown={onHeaderPointerDown}
        className="shrink-0 h-11 px-4 flex items-center justify-between border-b border-core/15 cursor-move select-none"
      >
        <div className="flex items-center gap-2 text-core">
          {Icon && <Icon size={15} />}
          <span className="font-display text-xs font-semibold tracking-[0.18em] uppercase text-[#DBF4FA]">{title}</span>
        </div>
        <button
          aria-label={`Close ${title}`}
          onClick={() => onClose(id)}
          className="text-[#7FA3B2] hover:text-core transition-colors"
        >
          <X size={16} />
        </button>
      </header>
      <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
    </div>
  )
}
