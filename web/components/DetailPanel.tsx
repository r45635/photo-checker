"use client"

import { useEffect, useState } from "react"
import { X, Star, Cloud, CloudOff, ExternalLink, CheckCircle2, Loader2, Image as ImageIcon, Play } from "lucide-react"
import type { PhotoRecord, ApplePhotoInfo } from "@/lib/types"
import {
  thumbnailUrl,
  appleThumbnailUrl,
  getAppleInfo,
  importPhoto,
  patchRecord,
  openInPhotos,
  playVideo,
} from "@/lib/api"

interface DetailPanelProps {
  record: PhotoRecord | null
  slug: string
  onClose: () => void
  onImported: (filename: string) => void
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

export default function DetailPanel({ record, slug, onClose, onImported }: DetailPanelProps) {
  const [appleInfo, setAppleInfo] = useState<ApplePhotoInfo | null>(null)
  const [appleLoading, setAppleLoading] = useState(false)
  const [appleError, setAppleError] = useState(false)
  const [importLoading, setImportLoading] = useState(false)
  const [importDone, setImportDone] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [thumbError, setThumbError] = useState(false)
  const [appleThumbError, setAppleThumbError] = useState(false)

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

  async function handleImport() {
    if (!record) return
    setImportLoading(true)
    setImportError(null)
    try {
      await importPhoto(record.path)
      await patchRecord(slug, record.filename)
      setImportDone(true)
      onImported(record.filename)
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
                <div className="rounded-xl overflow-hidden bg-[#080e1a] aspect-video flex items-center justify-center">
                  {isVideo(record.path) ? (
                    // Video: show thumbnail frame, play in QuickTime on click
                    <div className="relative w-full h-full group/vid cursor-pointer" onClick={() => playVideo(record.path)}>
                      {thumbError ? (
                        <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-[#4a6080]">
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
                      <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover/vid:opacity-100 transition-opacity duration-150">
                        <div className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                          <Play size={24} className="text-white ml-1" fill="white" />
                        </div>
                      </div>
                    </div>
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

              {/* Section B: Apple Photos (only if YES) */}
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
                    <p className="text-xs text-[#4a6080]">Not found in Apple Photos.</p>
                  )}
                  {!appleLoading && !appleError && appleInfo !== null && (
                    <div className="flex flex-col gap-3">
                      {/* Apple thumbnail */}
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

                      {/* Open in Photos button */}
                      <button
                        onClick={handleOpenInPhotos}
                        className="flex items-center justify-center gap-1.5 w-full px-3 py-2 rounded-lg border border-[#1a2840] text-xs text-slate-400 hover:text-slate-200 hover:border-[#2a3850] transition-colors duration-150"
                      >
                        Open in Photos
                        <ExternalLink size={11} />
                      </button>
                    </div>
                  )}
                </section>
              )}

              {/* Section C: Import CTA (only if NO) */}
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
            </div>
          </>
        )}
      </div>
    </>
  )
}
