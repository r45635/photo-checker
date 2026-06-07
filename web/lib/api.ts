import type { ApplePhotoInfo, PhotoRecord, ResultFile } from "./types"

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function throwIfNotOk(res: Response): Promise<void> {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text)
  }
}

export async function listResults(): Promise<ResultFile[]> {
  const res = await fetch(`${BASE}/api/results`)
  await throwIfNotOk(res)
  return res.json()
}

export async function getResults(slug: string): Promise<PhotoRecord[]> {
  const res = await fetch(`${BASE}/api/results/${encodeURIComponent(slug)}`)
  await throwIfNotOk(res)
  return res.json()
}

export function thumbnailUrl(path: string, size?: number): string {
  return BASE + "/api/thumbnail?path=" + encodeURIComponent(path) + "&size=" + (size ?? 400)
}

export function videoUrl(path: string): string {
  return BASE + "/api/video?path=" + encodeURIComponent(path)
}

export async function playVideo(path: string): Promise<void> {
  await fetch(`${BASE}/api/play-video`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  })
}

export function appleThumbnailUrl(filename: string, backupPath?: string, size?: number): string {
  let url = BASE + "/api/apple-thumbnail?filename=" + encodeURIComponent(filename) + "&size=" + (size ?? 400)
  if (backupPath) url += "&path=" + encodeURIComponent(backupPath)
  return url
}

export async function getAppleInfo(filename: string, backupPath?: string): Promise<ApplePhotoInfo | null> {
  let url = `${BASE}/api/apple-info?filename=${encodeURIComponent(filename)}`
  if (backupPath) url += "&path=" + encodeURIComponent(backupPath)
  const res = await fetch(url)
  if (res.status === 404) return null
  await throwIfNotOk(res)
  return res.json()
}

export async function scanFolder(
  folder: string,
  recursive: boolean
): Promise<{ slug: string; output: string }> {
  const res = await fetch(`${BASE}/api/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder, recursive }),
  })
  await throwIfNotOk(res)
  return res.json()
}

export async function importPhoto(path: string): Promise<void> {
  const res = await fetch(`${BASE}/api/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  })
  await throwIfNotOk(res)
}

export async function patchRecord(slug: string, filename: string): Promise<void> {
  const res = await fetch(`${BASE}/api/patch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slug, filename }),
  })
  await throwIfNotOk(res)
}

export async function deletePhotos(
  paths: string[],
  slug: string
): Promise<{ deleted: number; errors: any[] }> {
  const res = await fetch(`${BASE}/api/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths, slug }),
  })
  await throwIfNotOk(res)
  return res.json()
}

export async function movePhotos(
  paths: string[],
  dest: string,
  slug: string
): Promise<{ moved: number; errors: any[] }> {
  const res = await fetch(`${BASE}/api/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths, dest, slug }),
  })
  await throwIfNotOk(res)
  return res.json()
}

export async function openInFinder(path: string): Promise<void> {
  const res = await fetch(`${BASE}/api/open-finder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  })
  await throwIfNotOk(res)
}

export async function openInPhotos(uuid: string): Promise<void> {
  const res = await fetch(`${BASE}/api/open-photos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uuid }),
  })
  await throwIfNotOk(res)
}

export async function pickFolder(): Promise<string> {
  const res = await fetch(`${BASE}/api/pick-folder`)
  if (!res.ok) return ""
  const data = await res.json()
  return data.path ?? ""
}
