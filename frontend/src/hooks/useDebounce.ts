import { useEffect, useState } from 'react'

export function useDebounce<TValue>(value: TValue, delayMs = 300): TValue {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedValue(value), delayMs)
    return () => clearTimeout(timeout)
  }, [value, delayMs])

  return debouncedValue
}
