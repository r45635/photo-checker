"use client"

import clsx from "clsx"
import { ArrowUpRight, Check, Film, ImageOff } from "lucide-react"
import { useState } from "react"
import type { PhotoRecord } from "@/lib/types"

export interface PhotoCardProps {
  record: PhotoRecord
  index: number
  selected: boolean
  onSelect: (filename: string) => void
  onShiftSelect: (index: number) => void
  onView: (record: PhotoRecord) => void
  thumbnailUrl: string
}

const STATUS_BORDER: Record<PhotoRecord["safe_to_delete"], string> = {
  YES: "border-t-[#10b981]",
  NO: "border-t-[#f43f5e]",
  MAYBE: "border-t-[#f59e0b]",
}

const VIDEO_EXTENSIONS = new Set([".mp4", ".mov", ".m4v"])

function isVideo(filename: string): boolean {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase()
  return VIDEO_EXTENSIONS.has(ext)
}

function formatMB(sizeKb: number): string {
  return (sizeKb / 1024).toFixed(1) + " MB"
}

export default function PhotoCard({
  record,
  index,
  selected,
  onSelect,
  onShiftSelect,
  onView,
  thumbnailUrl,
}: PhotoCardProps) {
  const [imgError, setImgError] = useState(false)
  const video = isVideo(record.filename)

  return (
    <div
      className={clsx(
        "group relative rounded-xl overflow-hidden cursor-pointer",
        "border-t-[3px] bg-[#0d1625]",
        "transition-all duration-200 ease-out",
        "hover:scale-[1.02] hover:shadow-2xl hover:shadow-black/50",
        STATUS_BORDER[record.safe_to_delete],
        selected && "ring-2 ring-blue-500 ring-offset-1 ring-offset-[#060a10]"
      )}
      onClick={() => onView(record)}
    >
      {/* Thumbnail */}
      <div className="aspect-square bg-[#080e1a] relative overflow-hidden">
        {imgError ? (
          <div className="w-full h-full flex items-center justify-center">
            <ImageOff size={32} className="text-[#4a6080]" />
          </div>
        ) : (
          <img
            src={thumbnailUrl}
            alt={record.filename}
            className="w-full h-full object-cover"
            loading="lazy"
            onError={() => setImgError(true)}
          />
        )}

        {/* Video badge — always visible */}
        {video && (
          <div className="absolute bottom-2 right-2 pointer-events-none">
            <div className="w-6 h-6 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center">
              <Film size={12} className="text-white/70" />
            </div>
          </div>
        )}

        {/* Hover overlay */}
        <div
          className={clsx(
            "absolute inset-0 bg-black/40",
            "opacity-0 group-hover:opacity-100",
            "transition-opacity duration-150 ease-out"
          )}
        >
          {/* Select button — top-left */}
          <button
            className={clsx(
              "absolute top-2 left-2",
              "w-7 h-7 rounded-full flex items-center justify-center",
              "backdrop-blur-sm transition-transform duration-150 hover:scale-110",
              selected ? "bg-blue-500" : "bg-white/10"
            )}
            onClick={(e) => {
              e.stopPropagation()
              if (e.shiftKey) {
                onShiftSelect(index)
              } else {
                onSelect(record.filename)
              }
            }}
            aria-label={selected ? "Deselect" : "Select"}
          >
            {selected ? (
              <Check size={14} className="text-white" strokeWidth={2.5} />
            ) : (
              <span className="block w-3 h-3 rounded-full border border-white/60" />
            )}
          </button>

          {/* View button — bottom-right (hidden when video badge present) */}
          <button
            className={clsx(
              "absolute bottom-2 right-2",
              "w-7 h-7 rounded-full flex items-center justify-center",
              "bg-white/10 backdrop-blur-sm",
              "transition-transform duration-150 hover:scale-110",
              video && "right-10"
            )}
            onClick={(e) => {
              e.stopPropagation()
              onView(record)
            }}
            aria-label="View details"
          >
            <ArrowUpRight size={14} className="text-white" />
          </button>
        </div>
      </div>

      {/* Info bar */}
      <div className="px-3 py-2 bg-[#0a1020]">
        <p
          className="text-sm font-medium text-slate-200 truncate"
          title={record.filename}
        >
          {record.filename}
        </p>
        <div className="flex items-center mt-0.5 min-w-0">
          <span className="text-xs text-slate-500 shrink-0">
            {formatMB(record.size_kb)}
          </span>
          {record._subfolder && (
            <span className="text-xs text-slate-600 truncate ml-auto pl-2">
              {record._subfolder}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
