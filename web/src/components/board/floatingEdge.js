// Floating-edge geometry (adapted from the React Flow floating-edges example).
// Computes where an edge meets each node's boundary from node center + size, so
// a pipe always touches the node cleanly no matter where it's dragged.

function getNodeIntersection(intersectionNode, targetNode) {
  const { width, height } = intersectionNode.measured
  const intersectionPos = intersectionNode.internals.positionAbsolute
  const targetPos = targetNode.internals.positionAbsolute

  const w = width / 2
  const h = height / 2
  const x2 = intersectionPos.x + w
  const y2 = intersectionPos.y + h
  const x1 = targetPos.x + targetNode.measured.width / 2
  const y1 = targetPos.y + targetNode.measured.height / 2

  const xx1 = (x1 - x2) / (2 * w) - (y1 - y2) / (2 * h)
  const yy1 = (x1 - x2) / (2 * w) + (y1 - y2) / (2 * h)
  const a = 1 / (Math.abs(xx1) + Math.abs(yy1) || 1)
  const xx3 = a * xx1
  const yy3 = a * yy1
  const x = w * (xx3 + yy3) + x2
  const y = h * (-xx3 + yy3) + y2

  return { x, y }
}

/** Endpoints (sx,sy)->(tx,ty) where the edge meets each node's border. */
export function getEdgeParams(source, target) {
  const s = getNodeIntersection(source, target)
  const t = getNodeIntersection(target, source)
  return { sx: s.x, sy: s.y, tx: t.x, ty: t.y }
}
