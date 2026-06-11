"use client"

import { useEffect, useRef, useState } from "react"
import { Folder, Loader2, CheckCircle2, AlertCircle, X } from "lucide-react"
import { scanFolder } from "@/lib/api"

interface ScanDialogProps {
  open: boolean
  onClose: () => void
  onScanned: (slug: string) => void
}

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export default function ScanDialog({ open, onClose, onScanned }: ScanDialogProps) {
  const [folderPath, setFolderPath] = useState("")
  const [recursive, setRecursive] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [output, setOutput] = useState("")
  const [error, setError] = useState("")
  const [done, setDone] = useState(false)
  const [slug, setSlug] = useState("")
  const [visible, setVisible] = useState(false)
  const [progress, setProgress] = useState<{ current: number; total: number; file: string } | null>(null)

  const outputRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Animate in/out
  useEffect(() => {
    if (open) {
      // Defer to next frame so the transition fires
      const id = requestAnimationFrame(() => setVisible(true))
      return () => cancelAnimationFrame(id)
    } else {
      setVisible(false)
    }
  }, [open])

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setFolderPath("")
      setRecursive(false)
      setScanning(false)
      setOutput("")
      setError("")
      setDone(false)
      setSlug("")
      setProgress(null)
      setTimeout(() => inputRef.current?.focus(), 150)
    }
  }, [open])

  // Scroll output to bottom as it grows
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [output])

  // Escape key closes dialog
  useEffect(() => {
    if (!open) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !scanning) onClose()
    }
    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [open, scanning, onClose])

  async function handlePickFolder() {
    try {
      const res = await fetch(`${BASE}/api/pick-folder`)
      if (res.ok) {
        const data = await res.json()
        if (data.path) setFolderPath(data.path)
      }
    } catch {
      // Native dialog unavailable — user can type path manually
    }
  }

  async function handleScan() {
    if (!folderPath.trim()) return
    setScanning(true)
    setOutput("")
    setError("")
    setDone(false)
    setSlug("")
    setProgress(null)

    try {
      const result = await scanFolder(
        folderPath.trim(),
        recursive,
        (current, total, file) => setProgress({ current, total, file })
      )
      setOutput(result.output ?? "")
      setSlug(result.slug)
      setDone(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setScanning(false)
      setProgress(null)
    }
  }

  function handleViewResults() {
    onScanned(slug)
    onClose()
  }

  function handleBackdropClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget && !scanning) onClose()
  }

  if (!open) return null

  const showOutputArea = scanning || output || error

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center"
      style={{ backgroundColor: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={handleBackdropClick}
    >
      <div
        className="w-full max-w-lg shadow-2xl"
        style={{
          background: "#0d1625",
          borderRadius: "1rem",
          border: "1px solid #1a2840",
          padding: "1.5rem",
          transition: "opacity 150ms ease-out, transform 150ms ease-out",
          opacity: visible ? 1 : 0,
          transform: visible ? "scale(1)" : "scale(0.95)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 style={{ color: "#e2e8f0", fontSize: "1.125rem", fontWeight: 600, margin: 0 }}>
            Scan a folder
          </h2>
          <button
            onClick={onClose}
            disabled={scanning}
            style={{
              background: "none",
              border: "none",
              color: "#4a6080",
              cursor: scanning ? "not-allowed" : "pointer",
              padding: "4px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              transition: "color 150ms ease-out",
            }}
            onMouseEnter={(e) => { if (!scanning) (e.currentTarget.style.color = "#e2e8f0") }}
            onMouseLeave={(e) => { (e.currentTarget.style.color = "#4a6080") }}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Folder input row */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
          <div
            style={{
              flex: 1,
              position: "relative",
              display: "flex",
              alignItems: "center",
            }}
          >
            <Folder
              size={15}
              style={{
                position: "absolute",
                left: "10px",
                color: "#4a6080",
                pointerEvents: "none",
                flexShrink: 0,
              }}
            />
            <input
              ref={inputRef}
              type="text"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              placeholder="/path/to/folder"
              disabled={scanning}
              onKeyDown={(e) => { if (e.key === "Enter" && folderPath.trim() && !scanning) handleScan() }}
              style={{
                width: "100%",
                background: "#080e1a",
                border: "1px solid #1a2840",
                borderRadius: "8px",
                padding: "8px 10px 8px 32px",
                fontSize: "0.875rem",
                color: "#e2e8f0",
                outline: "none",
                fontFamily: "-apple-system, 'SF Pro Text', system-ui, sans-serif",
                opacity: scanning ? 0.6 : 1,
                boxSizing: "border-box",
              }}
              // Inline focus ring via onFocus/onBlur
              onFocus={(e) => { e.currentTarget.style.borderColor = "#3b82f6" }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "#1a2840" }}
            />
          </div>
          <button
            onClick={handlePickFolder}
            disabled={scanning}
            style={{
              flexShrink: 0,
              background: "#111d30",
              border: "1px solid #1a2840",
              borderRadius: "8px",
              padding: "8px 12px",
              fontSize: "0.875rem",
              color: "#e2e8f0",
              cursor: scanning ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
              fontFamily: "-apple-system, 'SF Pro Text', system-ui, sans-serif",
              transition: "background 150ms ease-out",
              opacity: scanning ? 0.6 : 1,
            }}
            onMouseEnter={(e) => { if (!scanning) (e.currentTarget.style.background = "#1a2840") }}
            onMouseLeave={(e) => { (e.currentTarget.style.background = "#111d30") }}
          >
            Choose folder
          </button>
        </div>

        {/* Recursive checkbox */}
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginBottom: "20px",
            cursor: scanning ? "not-allowed" : "pointer",
            userSelect: "none",
          }}
        >
          <div
            style={{
              width: "16px",
              height: "16px",
              borderRadius: "4px",
              border: `1px solid ${recursive ? "#3b82f6" : "#1a2840"}`,
              background: recursive ? "#3b82f6" : "#080e1a",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              transition: "background 150ms ease-out, border-color 150ms ease-out",
              cursor: scanning ? "not-allowed" : "pointer",
            }}
            onClick={() => { if (!scanning) setRecursive((v) => !v) }}
          >
            {recursive && (
              <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
          <span style={{ fontSize: "0.875rem", color: "#cbd5e1" }}>Include subfolders</span>
        </label>

        {/* Progress bar */}
        {scanning && progress && (
          <div style={{ marginBottom: "12px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "#4a6080", marginBottom: "4px" }}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginRight: "8px" }}>
                {progress.current === 0 ? progress.file : progress.file}
              </span>
              <span style={{ flexShrink: 0 }}>
                {progress.current > 0 ? `${progress.current} / ${progress.total}` : `0 / ${progress.total}`}
              </span>
            </div>
            <div style={{ height: "4px", background: "#1a2840", borderRadius: "2px", overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  background: "#3b82f6",
                  borderRadius: "2px",
                  width: progress.total > 0 ? `${Math.round((progress.current / progress.total) * 100)}%` : "0%",
                  transition: "width 200ms ease-out",
                }}
              />
            </div>
          </div>
        )}

        {/* Output area */}
        {showOutputArea && (
          <div
            ref={outputRef}
            style={{
              background: "#080e1a",
              borderRadius: "8px",
              padding: "12px",
              fontSize: "0.75rem",
              color: "#94a3b8",
              fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace",
              maxHeight: "8rem",
              overflowY: "auto",
              marginBottom: "20px",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              lineHeight: 1.6,
            }}
          >
            {scanning && !output && (
              <span style={{ color: "#4a6080" }}>Starting scan…</span>
            )}
            {output}
            {scanning && output && <span style={{ color: "#4a6080" }}>…</span>}
          </div>
        )}

        {/* Error message */}
        {error && (
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "8px",
              background: "rgba(244,63,94,0.08)",
              border: "1px solid rgba(244,63,94,0.2)",
              borderRadius: "8px",
              padding: "10px 12px",
              marginBottom: "20px",
            }}
          >
            <AlertCircle size={15} style={{ color: "#f43f5e", flexShrink: 0, marginTop: "1px" }} />
            <span style={{ fontSize: "0.8125rem", color: "#f43f5e", lineHeight: 1.5 }}>{error}</span>
          </div>
        )}

        {/* Success state */}
        {done && !error && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "20px",
            }}
          >
            <CheckCircle2 size={15} style={{ color: "#10b981", flexShrink: 0 }} />
            <span style={{ fontSize: "0.8125rem", color: "#10b981", fontWeight: 500 }}>
              Scan complete
            </span>
          </div>
        )}

        {/* Footer actions */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
          {done && !error && (
            <button
              onClick={handleViewResults}
              style={{
                background: "#10b981",
                border: "none",
                borderRadius: "8px",
                padding: "8px 16px",
                fontSize: "0.875rem",
                fontWeight: 500,
                color: "#fff",
                cursor: "pointer",
                fontFamily: "-apple-system, 'SF Pro Text', system-ui, sans-serif",
                transition: "background 150ms ease-out",
              }}
              onMouseEnter={(e) => { (e.currentTarget.style.background = "#059669") }}
              onMouseLeave={(e) => { (e.currentTarget.style.background = "#10b981") }}
            >
              View results
            </button>
          )}
          {!done && (
            <button
              onClick={handleScan}
              disabled={!folderPath.trim() || scanning}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                background: !folderPath.trim() || scanning ? "#1e3a5f" : "#3b82f6",
                border: "none",
                borderRadius: "8px",
                padding: "8px 20px",
                fontSize: "0.875rem",
                fontWeight: 500,
                color: !folderPath.trim() || scanning ? "#4a6080" : "#fff",
                cursor: !folderPath.trim() || scanning ? "not-allowed" : "pointer",
                fontFamily: "-apple-system, 'SF Pro Text', system-ui, sans-serif",
                transition: "background 150ms ease-out, color 150ms ease-out",
              }}
              onMouseEnter={(e) => {
                if (folderPath.trim() && !scanning) (e.currentTarget.style.background = "#2563eb")
              }}
              onMouseLeave={(e) => {
                if (folderPath.trim() && !scanning) (e.currentTarget.style.background = "#3b82f6")
              }}
            >
              {scanning && <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />}
              {scanning ? "Scanning…" : "Scan"}
            </button>
          )}
        </div>
      </div>

      {/* Spin keyframe */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
