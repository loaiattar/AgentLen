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

/**
 * Renders a page at `/` inside a real, in-memory router with stub `/sessions`
 * and `/quality` routes, so a drill-down link can be clicked and the location
 * it lands on read back from `router.state.location`.
 */
export function renderWithRouter(Page: () => ReactNode) {
  // The router restores scroll on navigation; jsdom does not implement it.
  window.scrollTo = () => {}
  const rootRoute = createRootRoute({ component: Outlet })
  const routeTree = rootRoute.addChildren([
    createRoute({ getParentRoute: () => rootRoute, path: '/', component: Page }),
    createRoute({ getParentRoute: () => rootRoute, path: '/sessions', component: () => <p>Sessions list</p> }),
    createRoute({ getParentRoute: () => rootRoute, path: '/quality', component: () => <p>Quality</p> }),
  ])
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: ['/'] }) })
  render(<RouterProvider router={router} />)
  return router
}
