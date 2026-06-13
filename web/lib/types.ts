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
  width?: number | null
  height?: number | null
  match_confidence?: "high" | "medium" | "none" | "unknown"
  match_reason?: string
  is_cloud_only?: boolean
}

export interface ResultFile {
  slug: string
  name: string
  mtime: number        // Unix timestamp
  scan_date: string    // ISO datetime of the last scan, empty string if unknown
  folder: string       // actual folder that was scanned
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

export interface ExifInfo {
  width: number | null
  height: number | null
  datetime_original: string | null
  make: string | null
  model: string | null
  lens_make: string | null
  lens_model: string | null
  f_number: number | null
  exposure_time: string | null
  iso: number | null
  focal_length: number | null
  focal_length_35mm: number | null
  flash: boolean | null
  gps_lat: number | null
  gps_lon: number | null
  gps_alt: number | null
  duration_sec: number | null
  codec: string | null
}

export type FilterStatus = "ALL" | "YES" | "NO" | "MAYBE"
export type SortBy = "name" | "date" | "size" | "type"

export interface BatchAction {
  type: "delete" | "import" | "force_delete" | "move"
  step: 1 | 2
  destFolder?: string
}
