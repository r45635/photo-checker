export interface PhotoRecord {
  filename: string
  path: string
  size_kb: number
  apple_photos: string      // "yes" | "no" | "error" | "skipped"
  google_photos: string
  onedrive: string
  found_in: string          // "apple_photos" | "google_photos" | "onedrive" | ""
  safe_to_delete: "YES" | "NO" | "MAYBE"
  _subfolder: string        // "" for root level files
}

export interface ResultFile {
  slug: string
  name: string
  mtime: number        // Unix timestamp
  folder: string       // root folder that was scanned
  total: number
  yes: number
  no: number
  maybe: number
  size_yes_mb: number
}

export interface ApplePhotoInfo {
  uuid: string | null
  date: string | null
  albums: string[]
  keywords: string[]
  favorite: boolean
  ismissing: boolean
  iscloudasset: boolean
  has_local_copy: boolean
}

export type FilterStatus = "ALL" | "YES" | "NO" | "MAYBE"
export type SortBy = "name" | "date" | "subfolder"

export interface BatchAction {
  type: "delete" | "import" | "force_delete" | "move"
  step: 1 | 2
  destFolder?: string
}
