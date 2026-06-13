"use client"

import { useEffect } from "react"
import { X, ChevronLeft, ChevronRight } from "lucide-react"
import { thumbnailUrl, videoUrl } from "@/lib/api"
import VideoPlayer from "./VideoPlayer"

interface LightboxProps {
  paths: string[]
  index: number
  onChangeIndex: (i: number) => void
  onClose: () => void
}

function isVideo(path: string) {
  return /\.(mp4|mov|avi|mkv|m4v|webm)$/i.test(path)
}

export default function Lightbox({ paths, index, onChangeIndex, onClose }: LightboxProps) {
  const path = paths[index]
  const canPrev = index > 0
  const canNext = index < paths.length - 1
  const filename = path?.split("/").pop() ?? ""

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") { onClose(); return }
      if (e.key === "ArrowLeft" && canPrev) onChangeIndex(index - 1)
      if (e.key === "ArrowRight" && canNext) onChangeIndex(index + 1)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [index, canPrev, canNext, onClose, onChangeIndex])

  if (!path) return null

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.96)" }}
      onClick={onClose}
    >
      {/* Media — stop propagation so clicking the image doesn't close */}
      <div
        className="relative flex items-center justify-center"
        style={{ maxWidth: "95vw", maxHeight: "95vh" }}
        onClick={(e) => e.stopPropagation()}
      >
        {isVideo(path) ? (
          <VideoPlayer
            videoSrc={videoUrl(path)}
            posterSrc={thumbnailUrl(path)}
            className="max-w-[90vw] max-h-[90vh]"
          />
        ) : (
          <img
            src={thumbnailUrl(path, 2000)}
            alt={filename}
            style={{
              maxWidth: "90vw",
              maxHeight: "90vh",
              objectFit: "contain",
              borderRadius: "6px",
              boxShadow: "0 8px 80px rgba(0,0,0,0.8)",
            }}
          />
        )}
      </div>

      {/* Filename — top center */}
      <div
        className="absolute top-4 left-1/2 -translate-x-1/2 text-xs text-white/50 pointer-events-none"
        style={{ maxWidth: "60vw", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
      >
        {filename}
      </div>

      {/* Close */}
      <button
        onClick={onClose}
        className="absolute top-3 right-3 p-2 rounded-full text-white/60 hover:text-white transition-colors"
        style={{ background: "rgba(0,0,0,0.4)" }}
        aria-label="Close"
      >
        <X size={18} />
      </button>

      {/* Prev */}
      {canPrev && (
        <button
          onClick={(e) => { e.stopPropagation(); onChangeIndex(index - 1) }}
          className="absolute left-4 top-1/2 -translate-y-1/2 p-3 rounded-full text-white/70 hover:text-white transition-colors"
          style={{ background: "rgba(0,0,0,0.45)" }}
          aria-label="Previous"
        >
          <ChevronLeft size={22} />
        </button>
      )}

      {/* Next */}
      {canNext && (
        <button
          onClick={(e) => { e.stopPropagation(); onChangeIndex(index + 1) }}
          className="absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-full text-white/70 hover:text-white transition-colors"
          style={{ background: "rgba(0,0,0,0.45)" }}
          aria-label="Next"
        >
          <ChevronRight size={22} />
        </button>
      )}

      {/* Counter — bottom center */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-xs text-white/30 pointer-events-none">
        {index + 1} / {paths.length}
      </div>
    </div>
  )
}
