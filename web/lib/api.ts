import type { ApplePhotoInfo, ExifInfo, PhotoRecord, ResultFile } from "./types"

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function throwIfNotOk(res: Response): Promise<void> {
  if (!res.ok) {
    const text = await res.text()
    try {
      const json = JSON.parse(text)
      throw new Error(json.detail ?? text)
    } catch (e) {
      if (e instanceof SyntaxError) throw new Error(text)
      throw e
    }
  }
}

export async function listResults(): Promise<ResultFile[]> {
  const res = await fetch(`${BASE}/api/results`)
  await throwIfNotOk(res)
  return res.json()
}

export async function deleteResult(slug: string): Promise<void> {
  const res = await fetch(`${BASE}/api/results/${encodeURIComponent(slug)}`, { method: "DELETE" })
  await throwIfNotOk(res)
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
  recursive: boolean,
  onProgress?: (current: number, total: number, file: string) => void
): Promise<{ slug: string; output: string }> {
  const res = await fetch(`${BASE}/api/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder, recursive }),
  })

  if (!res.ok) {
    const text = await res.text()
    try {
      const j = JSON.parse(text)
      throw new Error(j.detail ?? text)
    } catch (e) {
      if (e instanceof SyntaxError) throw new Error(text)
      throw e
    }
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split("\n")
    buffer = lines.pop() ?? ""
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue
      const data = JSON.parse(line.slice(6))
      if (data.type === "progress" && onProgress) {
        onProgress(data.current, data.total, data.file)
      } else if (data.type === "done") {
        return { slug: data.slug, output: data.output ?? "" }
      } else if (data.type === "error") {
        throw new Error(data.detail)
      }
    }
  }
  throw new Error("Scan stream ended unexpectedly")
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

export async function getExif(path: string): Promise<ExifInfo | null> {
  try {
    const r = await fetch(`${BASE}/api/exif?path=${encodeURIComponent(path)}`)
    return r.ok ? r.json() : null
  } catch {
    return null
  }
}

export async function pickFolder(): Promise<string> {
  const res = await fetch(`${BASE}/api/pick-folder`)
  if (!res.ok) return ""
  const data = await res.json()
  return data.path ?? ""
}
