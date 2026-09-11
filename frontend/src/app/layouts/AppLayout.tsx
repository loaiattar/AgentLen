import { Outlet } from '@tanstack/react-router'

import { Shell } from '@/components/ui/Shell'
import { useLogoutMutation } from '@/features/auth/api/auth.mutations'
import { useMeQuery } from '@/features/auth/api/auth.queries'
import { initialsFromEmail } from '@/features/auth/lib/initials'
import { useMetricsFilters } from '@/features/dashboard/hooks/useMetricsFilters'

export function AppLayout() {
  const { datasetLabel, periodLabel, datasetOptions, periodOptions, setDataSourceId, setPeriod } =
    useMetricsFilters()
  const me = useMeQuery()
  const logout = useLogoutMutation()
  const accountLabel = me.data?.email ? initialsFromEmail(me.data.email) : 'AS'

  return (
    <Shell
      datasetLabel={datasetLabel}
      periodLabel={periodLabel}
      datasetItems={datasetOptions.map((option) => ({
        label: option.label,
        onSelect: () => setDataSourceId(option.id),
      }))}
      periodItems={periodOptions.map((option) => ({
        label: option.label,
        onSelect: () => setPeriod(option.id),
      }))}
      accountLabel={accountLabel}
      accountItems={[
        ...(me.data?.email ? [{ label: me.data.email, disabled: true }] : []),
        {
          label: 'Sign out',
          tone: 'danger' as const,
          onSelect: () => {
            logout.mutate()
          },
        },
      ]}
    >
      <Outlet />
    </Shell>
  )
}
