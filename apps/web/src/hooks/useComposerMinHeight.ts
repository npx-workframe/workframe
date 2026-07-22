import { useLayoutEffect, useRef } from 'react'

export function useComposerMinHeight(onMinHeightChange?: (height: number) => void) {
  const rootRef = useRef<HTMLDivElement>(null)
  const toolbarRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useLayoutEffect(() => {
    const root = rootRef.current
    const toolbar = toolbarRef.current
    const textarea = textareaRef.current
    if (!root || !toolbar || !textarea || !onMinHeightChange) return

    const measure = () => {
      const rootStyles = getComputedStyle(root)
      const textareaStyles = getComputedStyle(textarea)

      const rootPadY =
        parseFloat(rootStyles.paddingTop) + parseFloat(rootStyles.paddingBottom)
      const gap = parseFloat(rootStyles.gap) || 0

      const lineHeight = parseFloat(textareaStyles.lineHeight) || 20
      const textareaPadY =
        parseFloat(textareaStyles.paddingTop) + parseFloat(textareaStyles.paddingBottom)
      const textareaBorderY =
        parseFloat(textareaStyles.borderTopWidth) + parseFloat(textareaStyles.borderBottomWidth)
      const textareaMin = lineHeight + textareaPadY + textareaBorderY

      const fixedChildren = Array.from(root.children).filter((child): child is HTMLElement => {
        if (!(child instanceof HTMLElement) || child === textarea) return false
        const styles = getComputedStyle(child)
        return styles.position !== 'absolute' && styles.display !== 'none' && child.offsetHeight > 0
      })
      const fixedHeight = fixedChildren.reduce((total, child) => total + child.offsetHeight, 0)
      const flowGapCount = fixedChildren.length
      const next = Math.ceil(rootPadY + fixedHeight + gap * flowGapCount + textareaMin)
      onMinHeightChange(next)
    }

    measure()

    const observer = new ResizeObserver(measure)
    observer.observe(root)
    observer.observe(toolbar)

    return () => observer.disconnect()
  }, [onMinHeightChange])

  return { rootRef, toolbarRef, textareaRef }
}
