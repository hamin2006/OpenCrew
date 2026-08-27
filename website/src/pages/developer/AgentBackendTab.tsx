import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bot, Sparkles, Terminal } from 'lucide-react'

import { api } from '../../api/client'
import ErrorNotice from '../../components/ErrorNotice'
import { SettingsCard, SettingsButtonGroup } from '../../components/settings'
import { useConfigSchema } from '../../components/settingRef/useConfigSchema'
import { i18nT } from '../../i18n/t'

/** The config field the switch owns. Also the schema path the options are gated on. */
const CONFIG_KEY = 'agent.acp_backend'

/**
 * Backend ids, verbatim from `acp/types.py`. `''` (kiro-cli) is the shipped
 * default and is a REAL value, not "unset" — the empty string is how the core
 * spells the kiro backend, so it must round-trip as itself.
 */
const KIRO = ''
const CLAUDE = 'claude'
const KAS = 'kas'

/**
 * Developer > Agent Backend — pick which ACP agent drives a session.
 *
 * ## Why this exists again
 *
 * The public core used to ship a multi-provider `ProviderPanel` and deleted it
 * when it collapsed to kiro-cli only (`refactor(website): collapse provider layer
 * to KiroACP-only`). The BACKEND kept a three-way seam the whole time — kiro-cli,
 * KAS and a dormant Claude Code path — so `agent.acp_backend` has been switchable
 * with no way to switch it. This is that control, minus the dead parts of the old
 * panel (Bedrock model ids, a CC migration wizard, a provider enum that now has
 * exactly one member).
 *
 * ## Why the vocabulary comes from the server
 *
 * Every backend the code KNOWS about is rendered, but only the ones the running
 * build can actually serve a session with are selectable — that set is read from
 * `GET /api/config/schema` (`enumValues`), which the backend derives from the same
 * field metadata `PATCH /api/config/kirocrew` validates against. So the enabled
 * options and the values the wire accepts cannot disagree, and an edition that
 * widens the field lights its backend up here with no frontend change.
 *
 * Claude Code is the case that makes this worth doing: the public core carries the
 * protocol seam but no provider, and the Amazon internal edition selects it with
 * an environment variable rather than this field. Hiding it would imply it does not
 * exist; enabling it would produce a 400 from a control that looked live. It is
 * shown, disabled, and says which it is.
 *
 * Deliberately NOT under `pages/settings/`: `gen-settings-registry.mjs` scans that
 * directory, and indexing a backend switch into Settings search would advertise it
 * as an ordinary preference — it changes which agent binary runs.
 */
export function AgentBackendTab() {
  const qc = useQueryClient()
  const [saveError, setSaveError] = useState('')
  const schema = useConfigSchema()

  const cfgQ = useQuery<{ agent?: { acp_backend?: string } }>({
    queryKey: ['kirocrewConfig'],
    queryFn: () => api.kirocrewConfig(),
  })

  const patchMut = useMutation({
    mutationFn: (value: string) => api.patchConfig(CONFIG_KEY, value),
    onSuccess: () => {
      setSaveError('')
      qc.invalidateQueries({ queryKey: ['kirocrewConfig'] })
    },
    // No optimistic write and no local mirror of the value: the button group reads
    // straight from the query, so a rejected PATCH needs no revert — the cache was
    // never moved off the server's answer.
    onError: () => setSaveError(i18nT('pages.developer.agentBackendTab.could_not_save_the_agent_backend')),
  })

  if (cfgQ.isLoading) {
    return (
      <div className="text-muted text-sm py-12 text-center">
        {i18nT('pages.developer.agentBackendTab.loading_configuration')}
      </div>
    )
  }

  const current = cfgQ.data?.agent?.acp_backend ?? KIRO

  /**
   * `undefined` while the schema is in flight — every option stays enabled rather
   * than flashing disabled and then live, which would read as a broken control on
   * a slow load. The PATCH allowlist is the real gate either way, so an optimistic
   * enable can only cost one visible refusal.
   */
  const selectable = schema?.get(CONFIG_KEY)?.enum
  const unavailable = (value: string) => (selectable ? !selectable.includes(value) : false)

  const DETAIL: Record<string, string> = {
    [KIRO]: i18nT('pages.developer.agentBackendTab.kiro_cli_over_acp_the_default_full_mcp_tools_int'),
    [CLAUDE]: i18nT('pages.developer.agentBackendTab.claude_code_over_acp_only_the_amazon_internal_ed'),
    [KAS]: i18nT('pages.developer.agentBackendTab.kiro_agent_over_acp_run_from_the_copy_kiro_cli_u'),
  }

  return (
    <>
      <ErrorNotice message={saveError} onDismiss={() => setSaveError('')} />
      <SettingsCard>
        <SettingsButtonGroup
          label={i18nT('pages.developer.agentBackendTab.agent_backend')}
          description={i18nT('pages.developer.agentBackendTab.which_acp_agent_drives_a_session_applies_to_new')}
          configKey={CONFIG_KEY}
          value={current}
          disabled={patchMut.isPending}
          options={[
            {
              value: KIRO,
              label: i18nT('pages.developer.agentBackendTab.kiro_cli'),
              icon: <Terminal size={14} />,
              disabled: unavailable(KIRO),
            },
            {
              value: CLAUDE,
              label: i18nT('pages.developer.agentBackendTab.claude_code'),
              icon: <Sparkles size={14} />,
              disabled: unavailable(CLAUDE),
            },
            {
              value: KAS,
              label: i18nT('pages.developer.agentBackendTab.kas_kiro_agent'),
              icon: <Bot size={14} />,
              disabled: unavailable(KAS),
            },
          ]}
          onChange={v => patchMut.mutate(v)}
        />
        {/* One line per backend, always all three — the reader is choosing BETWEEN
            them, so showing only the selected one's caveats would hide the very
            comparison the control is for. */}
        <dl className="mt-2 space-y-1.5">
          {[KIRO, CLAUDE, KAS].map(value => (
            <div key={value} className="flex gap-2 text-[11px] leading-relaxed">
              <dt className={`shrink-0 font-semibold ${value === current ? 'text-text-strong' : 'text-muted'}`}>
                {value === KIRO && i18nT('pages.developer.agentBackendTab.kiro_cli')}
                {value === CLAUDE && i18nT('pages.developer.agentBackendTab.claude_code')}
                {value === KAS && i18nT('pages.developer.agentBackendTab.kas_kiro_agent')}
              </dt>
              <dd className="text-muted m-0">
                {DETAIL[value]}
                {unavailable(value) && (
                  <span className="ml-1 text-warn">
                    {i18nT('pages.developer.agentBackendTab.not_available_in_this_build')}
                  </span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </SettingsCard>
    </>
  )
}
