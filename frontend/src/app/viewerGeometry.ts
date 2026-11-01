export type Point = { x: number; y: number }
export type Dimensions = { w: number; h: number }

/** Keep the photograph and every overlay in the same fitted coordinate system. */
export function viewerGeometry(image: Dimensions, viewport: Dimensions, zoom: number, pan: Point) {
  const fit = Math.min(viewport.w / Math.max(1, image.w), viewport.h / Math.max(1, image.h))
  const width = image.w * fit, height = image.h * fit
  const limitX = Math.max(0, (width * zoom - viewport.w) / 2)
  const limitY = Math.max(0, (height * zoom - viewport.h) / 2)
  return {
    width, height,
    pan: { x: Math.max(-limitX, Math.min(limitX, pan.x)), y: Math.max(-limitY, Math.min(limitY, pan.y)) },
  }
}
