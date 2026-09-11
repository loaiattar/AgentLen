import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { render } from '@testing-library/react'
import type { ReactNode } from 'react'

import { parseMetricsSearch } from '@/features/dashboard/lib/filters'

/**
 * Renders a page under a `/_app` layout that validates the search like the real
 * one, so `getRouteApi('/_app')` resolves and the raw URL (`location.search`)
 * can differ from what validation kept. Stub `/overview` and `/sessions` routes
 * take the navigations the page does not own.
 */
export function renderInAppLayout(Page: () => ReactNode, { path, url }: { path: 'overview' | 'sessions'; url: string }) {
  // The router restores scroll on navigation; jsdom does not implement it.
  window.scrollTo = () => {}
  const rootRoute = createRootRoute({ component: Outlet })
  const appRoute = createRoute({
    getParentRoute: () => rootRoute,
    id: '_app',
    validateSearch: parseMetricsSearch,
    component: Outlet,
  })
  const stub = (stubPath: string) =>
    createRoute({ getParentRoute: () => appRoute, path: stubPath, component: () => <p>{stubPath}</p> })
  const pages = (['overview', 'sessions'] as const).map((name) =>
    name === path ? createRoute({ getParentRoute: () => appRoute, path, component: Page }) : stub(name),
  )
  const routeTree = rootRoute.addChildren([appRoute.addChildren(pages)])
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [url] }) })
  render(<RouterProvider router={router} />)
  return router
}
