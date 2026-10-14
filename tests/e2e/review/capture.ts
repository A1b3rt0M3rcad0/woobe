import type { Locator, Page } from '@playwright/test'
import { mkdir, readdir, unlink } from 'node:fs/promises'
import { resolve } from 'node:path'

export async function resetCaptures(directory: string, prefix: string) {
  if(process.env.WOOBE_CAPTURE_AUXILIARY!=='1')return
  await mkdir(directory,{recursive:true})
  for(const file of await readdir(directory))if(file===`${prefix}.png` || (file.startsWith(`${prefix}-`) && file.endsWith('.png')))await unlink(resolve(directory,file))
}

/** Record the real scrolling regions, including a standard dialog's outer overlay. */
export async function captureScrollSequence(page: Page, overlay: Locator, directory: string, prefix: string) {
  if (process.env.WOOBE_CAPTURE_AUXILIARY !== '1') return
  await mkdir(directory, { recursive: true })
  await page.locator('[data-review-scroll],[data-review-horizontal]').evaluateAll(nodes=>nodes.forEach(node=>{node.removeAttribute('data-review-scroll');node.removeAttribute('data-review-horizontal')}))
  const save = (suffix: string) => page.screenshot({ path: resolve(directory, `${prefix}-${suffix}.png`), animations: 'disabled', fullPage: true })
  const navigation = await overlay.locator('nav').evaluateAll(nodes => nodes.flatMap((nav, index) => {
    const parent = nav.parentElement
    if (!parent || parent.scrollWidth <= parent.clientWidth + 4 || !/auto|scroll/.test(getComputedStyle(parent).overflowX)) return []
    parent.setAttribute('data-review-horizontal', String(index))
    return [{ index, total: parent.scrollWidth, width: parent.clientWidth }]
  }))
  for (const area of navigation) {
    const scroller = overlay.locator(`[data-review-horizontal="${area.index}"]`)
    for (let left = area.width - 60, index = 1; left < area.total; left += area.width - 60, index++) {
      await scroller.evaluate((el, x) => { el.scrollLeft = x }, left)
      await save(`pan-${area.index}-${index}`)
    }
    await scroller.evaluate(el => { el.scrollLeft = 0 })
  }
  const regions = await overlay.evaluate(root => {
    const nodes = [root.parentElement, root, ...root.querySelectorAll('*')].filter((node): node is HTMLElement => node instanceof HTMLElement)
    return nodes.filter(el => el.clientHeight > 100 && el.scrollHeight > el.clientHeight + 4 && /auto|scroll/.test(getComputedStyle(el).overflowY))
      .map((el, index) => {
        el.setAttribute('data-review-scroll', String(index))
        return { index, total: el.scrollHeight, height: el.clientHeight }
      })
  })
  for (const area of regions) {
    const scroller = page.locator(`[data-review-scroll="${area.index}"]`)
    for (let top = area.height - 60, index = 1; top < area.total; top += area.height - 60, index++) {
      await scroller.evaluate((el, y) => { el.scrollTop = y }, top)
      await save(`scroll-${area.index}-${index}`)
    }
    await scroller.evaluate(el => { el.scrollTop = 0 })
  }
}
