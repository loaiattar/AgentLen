export function parseAuthRedirectSearch(search: Record<string, unknown>): { redirect?: string } {
  if (typeof search.redirect === 'string' && isSafeAppPath(search.redirect)) {
    return { redirect: search.redirect }
  }
  return {}
}

export function isSafeAppPath(path: string): boolean {
  return path.startsWith('/') && !path.startsWith('//') && path !== '/login' && path !== '/register'
}

export function resolvePostAuthPath(redirect: string | undefined): string {
  if (redirect && isSafeAppPath(redirect) && redirect !== '/') return redirect
  return '/overview'
}
