"use client"

import { useEffect, useState } from "react"
import { X, Star, Cloud, CloudOff, ExternalLink, CheckCircle2, Loader2, Image as ImageIcon, FolderOpen } from "lucide-react"
import type { ApplePhotoInfo, ExifInfo, PhotoRecord } from "@/lib/types"
import {
  thumbnailUrl,
  videoUrl,
  appleThumbnailUrl,
  getAppleInfo,
  getExif,
  importPhoto,
  patchRecord,
  openInPhotos,
  openInFinder,
} from "@/lib/api"
import VideoPlayer from "./VideoPlayer"

interface DetailPanelProps {
  record: PhotoRecord | null
  slug: string
  onClose: () => void
  onImported: (path: string) => void
  onOpenLightbox?: (path: string) => void
}

const STATUS_STYLES: Record<string, string> = {
  YES: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
  NO: "bg-rose-500/20 text-rose-400 border border-rose-500/30",
  MAYBE: "bg-amber-500/20 text-amber-400 border border-amber-500/30",
}

function isVideo(path: string): boolean {
  return /\.(mp4|mov|avi|mkv|m4v|webm)$/i.test(path)
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "Unknown date"
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    })
  } catch {
    return dateStr
  }
}

function fmtDuration(sec: number): string {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
  return `${m}:${String(s).padStart(2, "0")}`
}

function fmtExifDate(s: string | null): string | null {
  if (!s) return null
  // "2024-03-15T14:32:08" → "2024-03-15  14:32:08"
  return s.replace("T", "  ")
}

function fmtExposure(s: string | null): string | null {
  if (!s) return null
  return s.includes("/") ? `${s} s` : `${s} s`
}

function fmtFocal(mm: number | null, mm35: number | null): string | null {
  if (!mm && !mm35) return null
  const base = mm ? `${mm % 1 === 0 ? mm : mm.toFixed(1)} mm` : null
  const equiv = mm35 ? `${mm35} mm equiv.` : null
  if (base && equiv) return `${base}  (${equiv})`
  return base ?? equiv
}

function fmtCoord(lat: number, lon: number): string {
  const latDir = lat >= 0 ? "N" : "S"
  const lonDir = lon >= 0 ? "E" : "W"
  return `${Math.abs(lat).toFixed(5)}° ${latDir},  ${Math.abs(lon).toFixed(5)}° ${lonDir}`
}

export default function DetailPanel({ record, slug, onClose, onImported, onOpenLightbox }: DetailPanelProps) {
  const [appleInfo, setAppleInfo] = useState<ApplePhotoInfo | null>(null)
  const [appleLoading, setAppleLoading] = useState(false)
  const [appleError, setAppleError] = useState(false)
  const [importLoading, setImportLoading] = useState(false)
  const [importDone, setImportDone] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [thumbError, setThumbError] = useState(false)
  const [appleThumbError, setAppleThumbError] = useState(false)
  const [exifInfo, setExifInfo] = useState<ExifInfo | null>(null)

  useEffect(() => {
    if (!record) return

    setAppleInfo(null)
    setAppleError(false)
    setImportDone(false)
    setImportError(null)
    setThumbError(false)
    setAppleThumbError(false)

    if (record.safe_to_delete === "YES") {
      setAppleLoading(true)
      getAppleInfo(record.filename, record.path)
        .then((info) => {
          setAppleInfo(info)
        })
        .catch(() => {
          setAppleError(true)
        })
        .finally(() => {
          setAppleLoading(false)
        })
    }
  }, [record?.filename, record?.safe_to_delete])

  useEffect(() => {
    if (!record) return
    setExifInfo(null)
    getExif(record.path).then(setExifInfo)
  }, [record?.path])

  async function handleImport() {
    if (!record) return
    setImportLoading(true)
    setImportError(null)
    try {
      await importPhoto(record.path)
      await patchRecord(slug, record.filename)
      setImportDone(true)
      onImported(record.path)
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "Import failed")
    } finally {
      setImportLoading(false)
    }
  }

  async function handleOpenInPhotos() {
    if (!appleInfo?.uuid) return
    try {
      await openInPhotos(appleInfo.uuid)
    } catch {
      // best-effort
    }
  }

  async function handleRevealInFinder() {
    if (!record) return
    try {
      await openInFinder(record.path)
    } catch {
      // best-effort
    }
  }

  const isOpen = record !== null

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={[
          "fixed inset-y-0 right-0 w-[520px] z-50",
          "bg-[#0a1220] border-l border-[#1a2840]",
          "flex flex-col h-full",
          "transition-transform duration-300 ease-out",
          isOpen ? "translate-x-0" : "translate-x-full",
        ].join(" ")}
      >
        {record && (
          <>
            {/* Header */}
            <div className="px-5 py-4 border-b border-[#1a2840] flex items-center gap-3 shrink-0">
              <span
                className={[
                  "text-xs font-bold px-2 py-0.5 rounded-full shrink-0",
                  STATUS_STYLES[record.safe_to_delete] ?? "bg-slate-700 text-slate-300",
                ].join(" ")}
                title={record.safe_to_delete === "MAYBE" ? "Found in at least one source, but a check errored — verify before deleting" : undefined}
              >
                {record.safe_to_delete}
              </span>
              <span className="font-medium text-slate-200 truncate flex-1 text-sm">
                {record.filename}
              </span>
              <button
                onClick={onClose}
                className="shrink-0 p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-[#1a2840] transition-colors duration-150"
                aria-label="Close panel"
              >
                <X size={16} />
              </button>
            </div>

            {/* Main content */}
            <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-5">

              {/* Section A: Backup copy */}
              <section>
                <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">
                  Backup copy
                </p>
                <div
                  className="rounded-xl overflow-hidden bg-[#080e1a] aspect-video flex items-center justify-center"
                  style={{ cursor: onOpenLightbox ? "zoom-in" : undefined }}
                  onDoubleClick={() => onOpenLightbox?.(record.path)}
                  title={onOpenLightbox ? "Double-click to view full screen" : undefined}
                >
                  {isVideo(record.path) ? (
                    <VideoPlayer
                      videoSrc={videoUrl(record.path)}
                      posterSrc={thumbnailUrl(record.path)}
                      className="w-full h-full"
                    />
                  ) : thumbError ? (
                    <div className="flex flex-col items-center gap-2 text-[#4a6080]">
                      <ImageIcon size={32} />
                      <span className="text-xs">Preview unavailable</span>
                    </div>
                  ) : (
                    <img
                      src={thumbnailUrl(record.path)}
                      alt={record.filename}
                      className="w-full h-full object-contain"
                      onError={() => setThumbError(true)}
                    />
                  )}
                </div>
                <div className="mt-2 space-y-0.5">
                  <p className="text-xs text-slate-600 break-all">{record.path}</p>
                  <p className="text-xs text-[#4a6080]">{(record.size_kb / 1024).toFixed(2)} MB</p>
                </div>
              </section>

              {/* Section B: EXIF / Photo Info (always, when data available) */}
              {exifInfo && (exifInfo.width || exifInfo.datetime_original || exifInfo.make || exifInfo.gps_lat !== null || exifInfo.duration_sec !== null) && (
                <section>
                  <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">Photo info</p>
                  <div className="space-y-1.5 text-xs">

                    {/* Date + Resolution */}
                    {fmtExifDate(exifInfo.datetime_original) && (
                      <div className="flex items-center justify-between">
                        <span className="text-[#4a6080]">Captured</span>
                        <span className="text-slate-400 font-mono">{fmtExifDate(exifInfo.datetime_original)}</span>
                      </div>
                    )}
                    {exifInfo.width && exifInfo.height && (
                      <div className="flex items-center justify-between">
                        <span className="text-[#4a6080]">Resolution</span>
                        <span className="text-slate-400">{exifInfo.width.toLocaleString()} × {exifInfo.height.toLocaleString()} px</span>
                      </div>
                    )}

                    {/* Camera */}
                    {(exifInfo.make || exifInfo.model) && (
                      <div className="flex items-start justify-between gap-2 pt-1">
                        <span className="text-[#4a6080] shrink-0">Camera</span>
                        <span className="text-slate-400 text-right">
                          {[exifInfo.make, exifInfo.model].filter(Boolean).join("  ")}
                        </span>
                      </div>
                    )}
                    {exifInfo.lens_model && (
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-[#4a6080] shrink-0">Lens</span>
                        <span className="text-slate-400 text-right">{exifInfo.lens_model}</span>
                      </div>
                    )}

                    {/* Shooting parameters */}
                    {(exifInfo.f_number || exifInfo.exposure_time || exifInfo.iso) && (
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[#4a6080]">Exposure</span>
                        <span className="text-slate-400">
                          {[
                            exifInfo.f_number ? `f/${exifInfo.f_number}` : null,
                            exifInfo.exposure_time ? fmtExposure(exifInfo.exposure_time) : null,
                            exifInfo.iso ? `ISO ${exifInfo.iso}` : null,
                          ].filter(Boolean).join("  ·  ")}
                        </span>
                      </div>
                    )}
                    {fmtFocal(exifInfo.focal_length, exifInfo.focal_length_35mm) && (
                      <div className="flex items-center justify-between">
                        <span className="text-[#4a6080]">Focal</span>
                        <span className="text-slate-400">{fmtFocal(exifInfo.focal_length, exifInfo.focal_length_35mm)}</span>
                      </div>
                    )}

                    {/* Video-specific */}
                    {exifInfo.duration_sec !== null && (
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[#4a6080]">Duration</span>
                        <span className="text-slate-400 font-mono">{fmtDuration(exifInfo.duration_sec)}</span>
                      </div>
                    )}
                    {exifInfo.codec && (
                      <div className="flex items-center justify-between">
                        <span className="text-[#4a6080]">Codec</span>
                        <span className="text-slate-400">{exifInfo.codec}</span>
                      </div>
                    )}

                    {/* GPS */}
                    {exifInfo.gps_lat !== null && exifInfo.gps_lon !== null && (
                      <div className="pt-1 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-[#4a6080]">Location</span>
                          <span className="text-slate-400 font-mono text-right">
                            {fmtCoord(exifInfo.gps_lat, exifInfo.gps_lon)}
                            {exifInfo.gps_alt !== null && (
                              <span className="text-slate-600">  · {exifInfo.gps_alt >= 0 ? "" : "-"}{Math.abs(exifInfo.gps_alt)} m</span>
                            )}
                          </span>
                        </div>
                        <div className="flex justify-end">
                          <a
                            href={`https://maps.apple.com/?q=${exifInfo.gps_lat},${exifInfo.gps_lon}`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 transition-colors duration-150"
                          >
                            View on map
                            <ExternalLink size={10} />
                          </a>
                        </div>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* Section C: Apple Photos (only if YES) */}
              {record.safe_to_delete === "YES" && (
                <section>
                  <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">
                    Apple Photos
                  </p>
                  {appleLoading && (
                    <div className="flex items-center gap-2 text-[#4a6080] text-sm py-4">
                      <Loader2 size={14} className="animate-spin" />
                      <span>Loading Apple Photos info…</span>
                    </div>
                  )}
                  {appleError && (
                    <p className="text-xs text-rose-400">Failed to load Apple Photos info.</p>
                  )}
                  {!appleLoading && !appleError && appleInfo === null && (
                    <p className="text-xs text-amber-400/80">
                      Found at scan time — re-scan to recheck current status.
                    </p>
                  )}
                  {!appleLoading && !appleError && appleInfo !== null && (
                    <div className="flex flex-col gap-3">
                      {/* Apple thumbnail — only when we have a UUID (osxphotos found it) */}
                      {appleInfo.uuid ? (
                        <div className="rounded-xl overflow-hidden bg-[#080e1a] aspect-video flex items-center justify-center relative">
                          {appleThumbError ? (
                            <div className="flex flex-col items-center gap-2 text-[#4a6080]">
                              <ImageIcon size={32} />
                              <span className="text-xs">Preview unavailable</span>
                            </div>
                          ) : (
                            <img
                              src={appleThumbnailUrl(record.filename, record.path)}
                              alt={`Apple Photos: ${record.filename}`}
                              className="w-full h-full object-contain"
                              onError={() => setAppleThumbError(true)}
                            />
                          )}
                          {/* iCloud badge */}
                          {appleInfo.iscloudasset && (
                            <div className="absolute top-2 right-2 flex items-center gap-1 bg-[#0a1220]/80 backdrop-blur-sm px-2 py-1 rounded-full text-xs text-blue-400 border border-blue-500/30">
                              <Cloud size={10} />
                              <span>iCloud</span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-xs text-emerald-400/70">
                          Confirmed in Apple Photos library.
                        </p>
                      )}

                      {/* iCloud only warning */}
                      {appleInfo.iscloudasset && !appleInfo.has_local_copy && (
                        <div className="flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-lg px-3 py-2 text-xs text-blue-400">
                          <CloudOff size={12} />
                          <span>Stored in iCloud only — no local copy in Photos library</span>
                        </div>
                      )}

                      {/* Meta */}
                      <div className="space-y-1.5 text-xs">
                        {appleInfo.date && (
                          <div className="flex items-center justify-between">
                            <span className="text-[#4a6080]">Date</span>
                            <span className="text-slate-400">{formatDate(appleInfo.date)}</span>
                          </div>
                        )}
                        {appleInfo.albums.length > 0 && (
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-[#4a6080] shrink-0">Albums</span>
                            <span className="text-slate-400 text-right">{appleInfo.albums.join(", ")}</span>
                          </div>
                        )}
                        {appleInfo.keywords.length > 0 && (
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-[#4a6080] shrink-0">Keywords</span>
                            <span className="text-slate-400 text-right">{appleInfo.keywords.join(", ")}</span>
                          </div>
                        )}
                        {appleInfo.favorite && (
                          <div className="flex items-center gap-1.5 text-amber-400">
                            <Star size={12} fill="currentColor" />
                            <span>Favorited</span>
                          </div>
                        )}
                      </div>

                      {/* Open in Photos button — requires UUID from osxphotos */}
                      {appleInfo.uuid && (
                        <button
                          onClick={handleOpenInPhotos}
                          className="flex items-center justify-center gap-1.5 w-full px-3 py-2 rounded-lg border border-[#1a2840] text-xs text-slate-400 hover:text-slate-200 hover:border-[#2a3850] transition-colors duration-150"
                        >
                          Open in Photos
                          <ExternalLink size={11} />
                        </button>
                      )}
                    </div>
                  )}
                </section>
              )}

              {/* Section D: Import CTA (only if NO) */}
              {record.safe_to_delete === "NO" && (
                <section>
                  <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">
                    Import
                  </p>
                  {importDone ? (
                    <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-3 text-sm text-emerald-400">
                      <CheckCircle2 size={16} />
                      <span>Imported to Apple Photos</span>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <div className="bg-[#0d1625] border border-[#1a2840] rounded-xl px-4 py-3 text-xs text-[#4a6080]">
                        This photo has no backup in Apple Photos.
                      </div>
                      {importError && (
                        <p className="text-xs text-rose-400">{importError}</p>
                      )}
                      <button
                        onClick={handleImport}
                        disabled={importLoading}
                        className={[
                          "w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl",
                          "text-sm font-medium text-white",
                          "bg-blue-600 hover:bg-blue-500 active:bg-blue-700",
                          "transition-colors duration-150",
                          "disabled:opacity-50 disabled:cursor-not-allowed",
                        ].join(" ")}
                      >
                        {importLoading ? (
                          <>
                            <Loader2 size={15} className="animate-spin" />
                            Importing…
                          </>
                        ) : (
                          "Import to Apple Photos"
                        )}
                      </button>
                    </div>
                  )}
                </section>
              )}
            </div>

            {/* Footer */}
            <div className="px-5 py-4 border-t border-[#1a2840] shrink-0 space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#4a6080]">Size</span>
                <span className="text-slate-500">{(record.size_kb / 1024).toFixed(2)} MB</span>
              </div>
              {record._subfolder && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[#4a6080]">Subfolder</span>
                  <span className="text-slate-500 truncate max-w-[320px] text-right">{record._subfolder}</span>
                </div>
              )}
              <p className="text-xs text-slate-700 break-all pt-0.5">{record.path}</p>
              <button
                onClick={handleRevealInFinder}
                className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-[#1a2840] px-3 py-2 text-xs text-slate-500 hover:text-slate-300 hover:border-[#2a3850] transition-colors duration-150"
              >
                <FolderOpen size={11} />
                Reveal in Finder
              </button>
            </div>
          </>
        )}
      </div>
    </>
  )
}
