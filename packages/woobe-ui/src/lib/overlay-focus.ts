const overlayStack: string[] = []
let originalBodyOverflow: string | null = null

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

export function registerOverlay(id: string) {
  const existingIndex = overlayStack.lastIndexOf(id)
  if (existingIndex >= 0) overlayStack.splice(existingIndex, 1)
  if (overlayStack.length === 0) originalBodyOverflow = document.body.style.overflow
  overlayStack.push(id)
  document.body.style.overflow = 'hidden'
}

export function unregisterOverlay(id: string) {
  const index = overlayStack.lastIndexOf(id)
  if (index >= 0) overlayStack.splice(index, 1)
  if (overlayStack.length === 0 && originalBodyOverflow !== null) {
    document.body.style.overflow = originalBodyOverflow
    originalBodyOverflow = null
  }
}

export function isTopOverlay(id: string) {
  return overlayStack[overlayStack.length - 1] === id
}

export function focusableElements(root: HTMLElement) {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((element) => (
    element.getAttribute('aria-hidden') !== 'true'
    && !element.hasAttribute('hidden')
  ))
}
