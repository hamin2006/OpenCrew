/**
 * updatables — the pending-update derivation shared by `useAppsData` (the
 * store pages' data contract) and `App.tsx` (the sidebar Discover badge).
 *
 * The sidebar badge must show THE SAME count as the Discover Updates sub-tab,
 * and the only way two surfaces cannot drift is to compute both from one
 * shared function — the `mergeBuiltinRow` precedent: two inline derivations
 * in two files can contradict each other; one shared module cannot.
 *
 * This module is deliberately dependency-free (type-only imports, erased at
 * compile time): `App.tsx` lives in the eager App chunk while `useAppsData`
 * rides the lazy store-pages chunk, so importing the hook itself from the
 * shell would drag the whole store data layer into the App bundle.
 */
import type { InstalledApp, RegistryApp } from '../../components/appstore/types'

/** The registry-row fields the update derivation reads. */
export type UpdatableRegistryRow = Pick<RegistryApp, 'name' | 'version' | 'updateAvailable'>

/**
 * The installed-row fields the update derivation reads.
 *
 * Only server-emitted fields appear here: the `['apps']` cache can hold RAW
 * rows (some observers fetch it without normalizing — see the queryFn note in
 * `useAppsData`), so this derivation must not lean on anything normalization
 * adds.
 */
export type UpdatableInstalledRow = Pick<
  InstalledApp,
  'name' | 'lifecycle' | 'origin' | 'enabled' | 'manifest'
>

/**
 * Whether an installed app belongs in the Library list.
 *
 * A disabled builtin is normally hidden: the wheel ships ~20 of them default-off
 * and listing every one would bury the apps a reader actually uses. An app that
 * REPLACES a host surface is the exception, because it is the only class a reader
 * can turn off and then need to find again -- its own copy tells them to disable
 * it to get the old surface back, and with the row gone from Library and no
 * catalog row in Discover that would be a one-way switch. Keyed on `ui.overlays`
 * rather than on the app id so the rule belongs to the capability, not to a name.
 *
 * Exported so its test exercises this predicate rather than a copy of it.
 */
export function keepInLibrary(
  app: Pick<InstalledApp, 'origin' | 'enabled' | 'manifest'>,
): boolean {
  return !(app.origin === 'builtin' && !app.enabled && !app.manifest?.ui?.overlays?.length)
}

/** name → new version for every registry row with an update available. */
export function buildUpdateMap(
  registry: readonly UpdatableRegistryRow[],
): Map<string, string> {
  return new Map(registry.filter(r => r.updateAvailable).map(r => [r.name, r.version]))
}

/**
 * Whether Update All / the Updates sub-page would touch this Library row: a
 * pending update AND a gateway-managed lifecycle (`app`- and `locked`-
 * lifecycle apps manage their own updates, so the store cannot update them).
 */
export function isUpdatable(
  app: Pick<InstalledApp, 'name' | 'lifecycle'>,
  updateMap: ReadonlyMap<string, string>,
): boolean {
  return updateMap.has(app.name) && app.lifecycle === 'gateway'
}

/**
 * The updates count every badge surface shows (sidebar Discover row, Discover
 * Updates sub-tab) — the length of the same list `useAppsData.updatables`
 * builds, computed from the same two payloads. Tolerates absent inputs so a
 * cold cache (store pages never visited yet) reads as "no known updates".
 */
export function countUpdatables(
  registry: readonly UpdatableRegistryRow[] | undefined,
  installed: readonly UpdatableInstalledRow[] | undefined,
): number {
  if (!registry?.length || !installed?.length) return 0
  const updateMap = buildUpdateMap(registry)
  if (updateMap.size === 0) return 0
  return installed.filter(a => keepInLibrary(a) && isUpdatable(a, updateMap)).length
}
