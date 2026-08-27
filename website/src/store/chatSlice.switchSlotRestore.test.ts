/**
 * switchSlot.rejected restore behavior (#6309).
 *
 * When a non-404 rejection fires while the failed target is still active, the
 * reducer restores activeSlot to the pre-switch value and re-hydrates its
 * cached message page rather than leaving an empty pane. A 404 (slot genuinely
 * gone) keeps the existing clear behavior since there is nothing safe to
 * restore to.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

vi.mock('../api/client', () => ({ api: { chatSlotDetail: vi.fn() } }))

import chatReducer, { switchSlot } from './chatSlice'
import { api } from '../api/client'

const detail = vi.mocked(api.chatSlotDetail)

/** Structural ApiError shape -- same pattern as chatSlice.switchSlotRejection.test.ts */
const apiError = (status: number, message: string) =>
  Object.assign(new Error(message), { status })

function makeStore(extra: Record<string, unknown> = {}) {
  const base = chatReducer(undefined, { type: '@@INIT' })
  return configureStore({
    reducer: { chat: chatReducer },
    preloadedState: { chat: { ...base, ...extra } as typeof base },
    middleware: (getDefault) => getDefault({ immutableCheck: false }),
  })
}

const msg = (content: string, mid: string) =>
  ({ role: 'assistant' as const, content, cls: '', ts: '2026-01-01T00:00:00Z', meta: { mid } })

describe('switchSlot.rejected -- restore on transient failure (#6309)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('a transient rejection (500) restores activeSlot and messages', async () => {
    const cachedMessages = [msg('hello from origin', 'm-1')]
    const store = makeStore({
      activeSlot: 'slot-origin',
      messages: cachedMessages,
      slotMessages: { 'slot-origin': cachedMessages },
      slotHistory: [],
    })

    detail.mockRejectedValue(apiError(500, 'internal error'))
    await store.dispatch(switchSlot('slot-target'))

    const state = store.getState().chat
    expect(state.activeSlot).toBe('slot-origin')
    expect(state.messages).toEqual(cachedMessages)
    expect(state.slotLoading).toBe(false)
    // Origin is activeSlot again, so it must not appear in history
    expect(state.slotHistory).not.toContain('slot-origin')
  })

  it('a 404 rejection does NOT restore -- existing clear behavior', async () => {
    const cachedMessages = [msg('hello from origin', 'm-1')]
    const store = makeStore({
      activeSlot: 'slot-origin',
      messages: cachedMessages,
      slotMessages: { 'slot-origin': cachedMessages },
      slotHistory: [],
    })

    detail.mockRejectedValue(apiError(404, 'slot unavailable'))
    await store.dispatch(switchSlot('slot-target'))

    const state = store.getState().chat
    // 404: target stays active, messages cleared (slot is genuinely gone)
    expect(state.activeSlot).toBe('slot-target')
    expect(state.messages).toEqual([])
    expect(state.slotLoading).toBe(false)
  })

  it('a superseded switch (activeSlot already moved) early-returns', async () => {
    const cachedMessages = [msg('original', 'm-1')]
    const store = makeStore({
      activeSlot: 'slot-origin',
      messages: cachedMessages,
      slotMessages: { 'slot-origin': cachedMessages },
      slotHistory: [],
    })

    // First switch will reject with a delay; second switch will resolve immediately
    let rejectFirst!: (reason: unknown) => void
    detail.mockImplementationOnce(
      () => new Promise((_, reject) => { rejectFirst = reject }),
    )
    detail.mockResolvedValueOnce({
      key: 'slot-c',
      messages: [msg('from C', 'm-c')],
      running: false,
      has_more: false,
      total: 1,
      queue: [],
      next_before: 0,
    })

    const firstSwitch = store.dispatch(switchSlot('slot-b'))
    // Immediately switch again -- this makes activeSlot = 'slot-c'
    await store.dispatch(switchSlot('slot-c'))

    // Now reject the first switch
    rejectFirst(apiError(500, 'timeout'))
    await firstSwitch

    const state = store.getState().chat
    // The early-return guard fires: activeSlot !== 'slot-b', so no restore occurs
    expect(state.activeSlot).toBe('slot-c')
  })

  it('restore with no cached messages falls back to empty gracefully', async () => {
    const store = makeStore({
      activeSlot: 'slot-origin',
      messages: [msg('live message', 'm-1')],
      // No cached entry in slotMessages for origin
      slotMessages: {},
      slotHistory: [],
    })

    detail.mockRejectedValue(apiError(500, 'transient'))
    await store.dispatch(switchSlot('slot-target'))

    const state = store.getState().chat
    // Restore fires: activeSlot goes back, but messages default to [] since
    // there was nothing in slotMessages for the origin key.
    expect(state.activeSlot).toBe('slot-origin')
    expect(state.messages).toEqual([])
    expect(state.slotLoading).toBe(false)
  })

  it('slotHistory is unwound on restore (origin removed from history)', async () => {
    const cachedMessages = [msg('hello', 'm-1')]
    const store = makeStore({
      activeSlot: 'slot-origin',
      messages: cachedMessages,
      slotMessages: { 'slot-origin': cachedMessages },
      slotHistory: ['slot-x', 'slot-y'],
    })

    detail.mockRejectedValue(apiError(502, 'bad gateway'))
    await store.dispatch(switchSlot('slot-target'))

    const state = store.getState().chat
    expect(state.activeSlot).toBe('slot-origin')
    // Origin must NOT be in history (it is the activeSlot)
    expect(state.slotHistory).not.toContain('slot-origin')
    // The pending handler pushed origin and removed target from history;
    // after restore, origin is filtered out since it is activeSlot again.
    // slot-x and slot-y should still be present in some form.
    // The pending handler does: filter out target ('slot-target' was not in
    // history anyway), then pushHistory(origin). So history becomes
    // ['slot-x', 'slot-y', 'slot-origin']. Then rejected filters out origin:
    // ['slot-x', 'slot-y'].
    expect(state.slotHistory).toEqual(['slot-x', 'slot-y'])
  })

  it('slotSwitchOrigin is null after rejection settles', async () => {
    const store = makeStore({
      activeSlot: 'slot-origin',
      messages: [],
      slotMessages: {},
      slotHistory: [],
    })

    detail.mockRejectedValue(apiError(500, 'fail'))
    await store.dispatch(switchSlot('slot-target'))

    const state = store.getState().chat
    expect(state.slotSwitchOrigin).toBeNull()
    expect(state.slotSwitchRequestId).toBeNull()
    expect(state.slotSwitchTarget).toBeNull()
  })

  it('a status-less failure (no status field) triggers restore path', async () => {
    const cachedMessages = [msg('cached', 'm-1')]
    const store = makeStore({
      activeSlot: 'slot-origin',
      messages: cachedMessages,
      slotMessages: { 'slot-origin': cachedMessages },
      slotHistory: [],
    })

    // No status property -- a network error, for example
    detail.mockRejectedValue(new TypeError('Failed to fetch'))
    await store.dispatch(switchSlot('slot-target'))

    const state = store.getState().chat
    // Not a 404, so restore fires
    expect(state.activeSlot).toBe('slot-origin')
    expect(state.messages).toEqual(cachedMessages)
  })
})
