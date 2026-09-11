/**
 * Reading a paged route to the end, with a ceiling.
 *
 * Every list route caps `limit` at 200 (API.md §1). A screen that needs the
 * whole list — a timeline read top to bottom, a select to choose from — asks
 * page after page instead, and says so when it stopped before the end.
 */

/** `MAX_LIMIT` of `interfaces/http/pagination.py`. */
export const MAX_PAGE_SIZE = 200

/** Ten pages. Past it a list is not something to scroll through in one go. */
export const MAX_LOADED_ITEMS = 2000

/** One page as a route answered it: an envelope's `total`, or `X-Total-Count`. */
export interface PageResult<T> {
  items: T[]
  /** `null` when the route reported no total. */
  total: number | null
}

export interface LoadedList<T> extends PageResult<T> {
  /** True when `items` may not be everything the route holds. */
  truncated: boolean
}

export async function loadAllPages<T>(
  fetchPage: (limit: number, offset: number) => Promise<PageResult<T>>,
  maxItems: number = MAX_LOADED_ITEMS,
): Promise<LoadedList<T>> {
  const items: T[] = []
  for (;;) {
    const limit = Math.min(MAX_PAGE_SIZE, maxItems - items.length)
    const page = await fetchPage(limit, items.length)
    items.push(...page.items)
    const pageWasFull = page.items.length >= limit
    // Without a total there is nothing to page towards: stop, and flag a full
    // page as possibly cut short rather than guess.
    if (page.total === null) return { items, total: null, truncated: pageWasFull }
    if (!pageWasFull || items.length >= page.total || items.length >= maxItems) {
      return { items, total: page.total, truncated: items.length < page.total }
    }
  }
}

/** "Showing 2,000 of 2,345 events.", or `null` when nothing was left out. */
export function truncationNotice(list: LoadedList<unknown>, noun: string): string | null {
  if (!list.truncated) return null
  const shown = list.items.length.toLocaleString('en-US')
  return list.total === null
    ? `Showing the first ${shown} ${noun}: the API reported no total.`
    : `Showing ${shown} of ${list.total.toLocaleString('en-US')} ${noun}.`
}

/** `?limit=&offset=` appended to a path that may already carry a query. */
export function withWindow(path: string, limit: number, offset: number): string {
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}limit=${limit}&offset=${offset}`
}
