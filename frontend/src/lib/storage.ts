// localStorage can be missing or throw (private mode, blocked site data):
// preferences are a convenience and must never break the page.
export function readPref(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writePref(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // Preference simply is not remembered.
  }
}
