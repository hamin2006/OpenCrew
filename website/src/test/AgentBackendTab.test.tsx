/**
 * AgentBackendTab — Developer > Agent Backend switch.
 *
 * The behaviour worth pinning is the SCHEMA GATING, not the three labels: the tab
 * renders every backend the code knows about but may only select the ones the
 * running build advertises in `GET /api/config/schema`. Two of these cases are the
 * ones a hardcoded option list would silently get wrong — a backend the build
 * cannot serve must not be selectable, and a backend a later edition adds must
 * become selectable with no change here.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

const { patchConfigMock, kirocrewConfigMock, schemaMock } = vi.hoisted(() => ({
  patchConfigMock: vi.fn(() => Promise.resolve({})),
  kirocrewConfigMock: vi.fn(() => Promise.resolve({ agent: { acp_backend: '' } })),
  schemaMock: vi.fn(),
}))

vi.mock('../api/client', () => ({
  api: { kirocrewConfig: kirocrewConfigMock, patchConfig: patchConfigMock },
}))

vi.mock('../components/settingRef/useConfigSchema', () => ({
  useConfigSchema: () => schemaMock(),
}))

import { AgentBackendTab } from '../pages/developer/AgentBackendTab'

/** A schema map advertising exactly `values` for the backend field. */
function schemaWith(values: string[] | undefined) {
  if (!values) return undefined
  return new Map([['agent.acp_backend', { path: 'agent.acp_backend', type: 'enum', enum: values }]])
}

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <AgentBackendTab />
    </QueryClientProvider>,
  )
}

const button = (name: string) => screen.getByRole('button', { name })

beforeEach(() => {
  patchConfigMock.mockClear()
  patchConfigMock.mockResolvedValue({})
  kirocrewConfigMock.mockClear()
  kirocrewConfigMock.mockResolvedValue({ agent: { acp_backend: '' } })
  // The shipped core: kiro-cli + KAS selectable, Claude Code known but dormant.
  schemaMock.mockReturnValue(schemaWith(['', 'kas']))
})

describe('AgentBackendTab', () => {
  it('offers all three backends', async () => {
    wrap()
    expect(await screen.findByRole('button', { name: 'Kiro CLI' })).toBeInTheDocument()
    expect(button('Claude Code')).toBeInTheDocument()
    expect(button('KAS (kiro-agent)')).toBeInTheDocument()
  })

  it('reflects the configured backend as the pressed option', async () => {
    kirocrewConfigMock.mockResolvedValue({ agent: { acp_backend: 'kas' } })
    wrap()
    await waitFor(() => expect(button('KAS (kiro-agent)')).toHaveAttribute('aria-pressed', 'true'))
    expect(button('Kiro CLI')).toHaveAttribute('aria-pressed', 'false')
  })

  it('treats a missing acp_backend as kiro-cli rather than as unset', async () => {
    // `''` is a real backend id, so an absent field must land on Kiro CLI — not
    // leave every option unpressed.
    kirocrewConfigMock.mockResolvedValue({ agent: {} })
    wrap()
    await waitFor(() => expect(button('Kiro CLI')).toHaveAttribute('aria-pressed', 'true'))
  })

  it('saves the picked backend to agent.acp_backend', async () => {
    wrap()
    fireEvent.click(await screen.findByRole('button', { name: 'KAS (kiro-agent)' }))
    await waitFor(() => expect(patchConfigMock).toHaveBeenCalledWith('agent.acp_backend', 'kas'))
  })

  it('disables a backend the build does not advertise, and says so', async () => {
    wrap()
    await waitFor(() => expect(button('Claude Code')).toBeDisabled())
    expect(button('Kiro CLI')).toBeEnabled()
    expect(button('KAS (kiro-agent)')).toBeEnabled()
    expect(screen.getByText('Not available in this build')).toBeInTheDocument()
  })

  it('does not attempt to save an unavailable backend', async () => {
    wrap()
    fireEvent.click(await screen.findByRole('button', { name: 'Claude Code' }))
    await waitFor(() => expect(button('Kiro CLI')).toBeEnabled())
    expect(patchConfigMock).not.toHaveBeenCalled()
  })

  it('enables a backend once the schema advertises it', async () => {
    // The internal-edition case. Nothing about this component changes — the
    // option lights up because the server widened the field.
    schemaMock.mockReturnValue(schemaWith(['', 'claude', 'kas']))
    wrap()
    await waitFor(() => expect(button('Claude Code')).toBeEnabled())
    expect(screen.queryByText('Not available in this build')).not.toBeInTheDocument()

    fireEvent.click(button('Claude Code'))
    await waitFor(() => expect(patchConfigMock).toHaveBeenCalledWith('agent.acp_backend', 'claude'))
  })

  it('leaves every option selectable while the schema is still loading', async () => {
    // Flashing disabled and then live reads as a broken control; the PATCH
    // allowlist is the real gate, so an optimistic enable costs one refusal.
    schemaMock.mockReturnValue(undefined)
    wrap()
    await waitFor(() => expect(button('Claude Code')).toBeEnabled())
    expect(screen.queryByText('Not available in this build')).not.toBeInTheDocument()
  })

  it('surfaces a rejected save', async () => {
    patchConfigMock.mockRejectedValueOnce(new Error('nope'))
    wrap()
    fireEvent.click(await screen.findByRole('button', { name: 'KAS (kiro-agent)' }))
    expect(await screen.findByText('Could not save the agent backend.')).toBeInTheDocument()
  })

  it('keeps showing the server value after a rejected save', async () => {
    // No optimistic write: the pressed option must still be the backend the
    // server last confirmed, not the one the click attempted.
    patchConfigMock.mockRejectedValueOnce(new Error('nope'))
    wrap()
    fireEvent.click(await screen.findByRole('button', { name: 'KAS (kiro-agent)' }))
    await screen.findByText('Could not save the agent backend.')
    expect(button('Kiro CLI')).toHaveAttribute('aria-pressed', 'true')
    expect(button('KAS (kiro-agent)')).toHaveAttribute('aria-pressed', 'false')
  })
})
