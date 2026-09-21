// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ChatComposer } from './ChatComposer'

let root: Root
let container: HTMLDivElement

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
})

describe('ChatComposer External Context clear action', () => {
  it('calls Clear without toggling the External Context panel', async () => {
    const onClear = vi.fn()

    await act(async () => {
      root.render(
        <ChatComposer
          isSending={false}
          onSend={vi.fn()}
          onStop={vi.fn()}
          externalContextContract={{
            age: {
              schema: { type: 'integer' },
              required: true,
              model: { expose: false },
            },
          }}
          externalContextValues={{ age: 18 }}
          onExternalContextValuesChange={vi.fn()}
          onClearExternalContextValues={onClear}
        />,
      )
    })

    const clear = Array.from(container.querySelectorAll('button'))
      .find((button) => button.textContent?.trim() === 'Clear')
    expect(clear).toBeTruthy()
    expect(container.querySelector('[aria-expanded="true"]')).toBeNull()

    await act(async () => {
      clear?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })

    expect(onClear).toHaveBeenCalledTimes(1)
    expect(container.querySelector('[aria-expanded="true"]')).toBeNull()
  })
})
