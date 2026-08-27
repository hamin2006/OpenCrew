/**
 * Gate→fold contract for the shared reasoning-burst predicate (#6406).
 *
 * groupDisplayItems' wrap gate (contentThinkingCount) routes multi-burst
 * reasoning batches into a {kind:'turn'} wrapper for the ONE purpose of
 * feeding TurnBlock's mergeTurnThinking fold. Both sides (and ChatPage's
 * message renderer) now share a single predicate, `hasReasoningContent` /
 * `isReasoningBurst`. Two layers pin the contract:
 *
 * 1. Behavioral: grouping output rendered straight through TurnBlock must show
 *    exactly one thinking row, so a SEMANTICALLY divergent fork (the gate
 *    wrapping batches the fold no longer merges, regrowing the duplicate
 *    "Thought process" rows of #6376) fails here rather than passing each
 *    side's isolated tests.
 * 2. Structural: a byte-identical re-inline of the condition in TurnBlock.tsx
 *    would keep the behavioral tests green today and only diverge later, so a
 *    source scan asserts TurnBlock imports the shared predicate and keeps no
 *    hand-written copy.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { readFile } from 'node:fs/promises'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import TurnBlock from '../pages/chat/TurnBlock'
import { groupDisplayItems, isReasoningBurst, hasReasoningContent } from '../pages/chat/groupDisplayItems'
import type { ChatMessage } from '../types'
import type { DisplayItem, TurnItem } from '../pages/chat/types'

const CHAT_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'pages', 'chat')

const msg = (role: string, content = ''): ChatMessage =>
  ({ role, content, cls: '' } as ChatMessage)

// Mirrors ChatPage's renderMessage contract: an empty `thinking` placeholder
// renders nothing (it shares the same predicate), so rows counted below are
// exactly the rows a user would see.
const renderItem = (it: TurnItem, i: number) => {
  if (it.kind === 'single' && it.msg.role === 'thinking' && !hasReasoningContent(it.msg)) return null
  return (
    <div
      data-testid={`row-${i}`}
      data-role={it.kind === 'single' ? it.msg.role : 'group'}
    >
      {it.kind === 'single' ? it.msg.content : 'group'}
    </div>
  )
}

const findTurn = (turns: DisplayItem[]): Extract<DisplayItem, { kind: 'turn' }> => {
  const turn = turns.find((t): t is Extract<DisplayItem, { kind: 'turn' }> => t.kind === 'turn')
  expect(turn).toBeDefined()
  return turn!
}

describe('reasoning-burst gate→fold contract (#6406)', () => {
  it('a reasoning-only multi-burst batch renders exactly ONE thinking row through TurnBlock', () => {
    // The exact #6376 shape: a trailing turn that has only emitted reasoning.
    // The gate must wrap it, and the fold the gate feeds must merge it — the
    // contract holds only when both sides agree on what a burst is.
    const { turns } = groupDisplayItems([
      msg('thinking', 'burst 1'),
      msg('thinking', 'burst 2'),
      msg('thinking', 'burst 3'),
    ])
    const turn = findTurn(turns)
    const { container } = render(<TurnBlock turn={turn} renderItem={renderItem} />)
    const thinkingRows = container.querySelectorAll('[data-role="thinking"]')
    expect(thinkingRows).toHaveLength(1)
    // The fold concatenates burst content, so the one row carries all of it.
    expect(thinkingRows[0].textContent).toContain('burst 1')
    expect(thinkingRows[0].textContent).toContain('burst 3')
  })

  it('empty placeholder bursts neither trip the gate nor count as bursts', () => {
    // One real burst + empties: the gate must NOT wrap (nothing to dedup). If
    // a future predicate fork made the gate count empties while the fold
    // ignores them, this batch would wrap despite having one real burst.
    const { turns } = groupDisplayItems([
      msg('user', 'u'),
      msg('thinking', 'one real'),
      msg('thinking', ''),
      msg('thinking', ''),
    ])
    expect(turns.some(t => t.kind === 'turn')).toBe(false)
  })

  it('mixed batch: real bursts fold to one row, an empty placeholder stays in place unrendered', () => {
    const { turns } = groupDisplayItems([
      msg('user', 'u'),
      msg('thinking', 'plan A'),
      msg('tool', 'tool step'),
      msg('thinking', ''),
      msg('thinking', 'plan B'),
      msg('assistant', 'answer'),
    ])
    const turn = findTurn(turns)
    // The fold leaves the empty placeholder at its original position…
    const emptyBursts = turn.items.filter(
      t => t.kind === 'single' && t.msg.role === 'thinking' && !t.msg.content,
    )
    expect(emptyBursts).toHaveLength(1)
    // …and rendering shows exactly one (merged) thinking row: the placeholder
    // renders nothing under the same shared predicate.
    const { container } = render(<TurnBlock turn={turn} renderItem={renderItem} />)
    expect(container.querySelectorAll('[data-role="thinking"]')).toHaveLength(1)
    // The answer is still rendered (the fold is a hoist, not a filter).
    expect(screen.getByText('answer')).toBeInTheDocument()
  })

  it('isReasoningBurst / hasReasoningContent classify the enumerated shapes', () => {
    // Direct predicate pins: content-bearing thinking counts (whitespace-only
    // is content-bearing today — refining that is legal, but it must happen in
    // the shared predicate so gate, fold, and renderer move together), empty
    // and non-thinking shapes do not.
    const single = (role: string, content: string): TurnItem =>
      ({ kind: 'single', msg: msg(role, content), idx: 0 })
    expect(isReasoningBurst(single('thinking', 'text'))).toBe(true)
    expect(isReasoningBurst(single('thinking', '  '))).toBe(true)
    expect(isReasoningBurst(single('thinking', ''))).toBe(false)
    expect(isReasoningBurst(single('assistant', 'text'))).toBe(false)
    expect(isReasoningBurst({ kind: 'group', msgs: [msg('thinking', 'text')], startIdx: 0 })).toBe(false)
    expect(hasReasoningContent(msg('thinking', 'text'))).toBe(true)
    expect(hasReasoningContent(msg('thinking', ''))).toBe(false)
  })

  it('TurnBlock keeps no hand-written copy of the predicate (structural pin)', async () => {
    // A byte-identical re-inline in mergeTurnThinking would keep every
    // behavioral test above green and only drift later — the regression #6406
    // exists to prevent. Pin the structure: TurnBlock must import the shared
    // predicate and must not re-spell the thinking-role condition itself.
    const turnBlock = await readFile(join(CHAT_DIR, 'TurnBlock.tsx'), 'utf8')
    expect(
      turnBlock,
      'TurnBlock.tsx must import isReasoningBurst from ./groupDisplayItems',
    ).toMatch(/import \{ isReasoningBurst \} from '\.\/groupDisplayItems'/)
    expect(
      turnBlock.match(/role === 'thinking'/g),
      "a hand-written role === 'thinking' condition in TurnBlock forks the shared predicate",
    ).toBeNull()
    // The definition itself lives in groupDisplayItems, nowhere else in chat/.
    const groupSrc = await readFile(join(CHAT_DIR, 'groupDisplayItems.ts'), 'utf8')
    expect(groupSrc.match(/role === 'thinking'/g)).toHaveLength(1)
  })
})
