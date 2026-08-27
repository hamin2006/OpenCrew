import { fireEvent, screen } from '@testing-library/react'
import { renderWithProviders } from '../test/helpers'
import KasLoginGate from './KasLoginGate'
import { api } from '../api/client'

vi.mock('../api/client', async importOriginal => {
  const mod = await importOriginal<typeof import('../api/client')>()
  return {
    ...mod,
    api: {
      ...mod.api,
      kasLoginStatus: vi.fn().mockResolvedValue({
        authenticated: false,
        provider: null,
        identity: null,
        transport: 'device',
      }),
      kasLoginBeginDevice: vi.fn().mockResolvedValue({
        login_id: 'login-1',
        user_code: 'ABCD-EFGH',
        verification_uri_complete: 'https://app.kiro.dev/account/device?user_code=ABCD-EFGH',
        expires_at: '2099-01-01T00:00:00Z',
      }),
      kasLoginPoll: vi.fn().mockResolvedValue({ status: 'pending' }),
    },
  }
})

const kasLoginStatus = vi.mocked(api.kasLoginStatus)
const kasLoginBeginDevice = vi.mocked(api.kasLoginBeginDevice)

describe('KasLoginGate', () => {
  beforeEach(() => {
    kasLoginStatus.mockResolvedValue({
      authenticated: false,
      provider: null,
      identity: null,
      transport: 'device',
    })
    kasLoginBeginDevice.mockClear()
  })

  it('renders the chooser with all four sign-in options', async () => {
    renderWithProviders(<KasLoginGate />)

    expect(
      await screen.findByRole('button', { name: 'Continue with Google' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue with GitHub' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Continue with AWS Builder ID' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Continue with your work account' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Sign in to Kiro' }),
    ).toBeInTheDocument()
  })

  it('starts the device flow and shows the user code to approve', async () => {
    renderWithProviders(<KasLoginGate />)

    fireEvent.click(await screen.findByRole('button', { name: 'Continue with Google' }))

    expect(await screen.findByTestId('kas-login-user-code')).toHaveTextContent('ABCD-EFGH')
    expect(kasLoginBeginDevice).toHaveBeenCalledWith('google')
    expect(
      screen.getByRole('heading', { name: 'Finish signing in on your phone or another computer' }),
    ).toBeInTheDocument()
    // Step 1's link is rendered as a copyable block, verbatim.
    expect(
      screen.getByText('https://app.kiro.dev/account/device?user_code=ABCD-EFGH'),
    ).toBeInTheDocument()
  })

  it('renders its children once the gateway reports an active sign-in', async () => {
    kasLoginStatus.mockResolvedValue({
      authenticated: true,
      provider: 'google',
      identity: 'user@example.com',
      transport: 'device',
    })
    renderWithProviders(
      <KasLoginGate>
        <div data-testid="app-root" />
      </KasLoginGate>,
    )

    expect(await screen.findByTestId('app-root')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Continue with Google' }),
    ).not.toBeInTheDocument()
  })
})
