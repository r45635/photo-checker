"use client"

import { useEffect, useRef, useState } from "react"
import { Folder, Loader2, CheckCircle2, AlertCircle, X, Cloud, ChevronDown, ChevronUp } from "lucide-react"
import {
  scanFolder,
  getOnedriveStatus,
  saveOnedriveConfig,
  connectOnedrive,
  type OnedriveStatus,
} from "@/lib/api"

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

  // OneDrive state (via rclone)
  const [odStatus, setOdStatus] = useState<OnedriveStatus | null>(null)
  const [odEnabled, setOdEnabled] = useState(false)
  const [odExpanded, setOdExpanded] = useState(false)
  const [odPath, setOdPath] = useState("")
  const [odConnecting, setOdConnecting] = useState(false)
  const [odConnectError, setOdConnectError] = useState("")

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

  // Reset state when dialog opens + fetch OneDrive status
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
      setOdEnabled(false)
      setOdExpanded(false)
      setTimeout(() => inputRef.current?.focus(), 150)
      getOnedriveStatus()
        .then((s) => { setOdStatus(s); setOdPath(s.path ?? "") })
        .catch(() => setOdStatus(null))
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

  async function persistOnedrive(remote: string, path: string) {
    try {
      await saveOnedriveConfig(remote, path)
      const status = await getOnedriveStatus()
      setOdStatus(status)
    } catch { /* ignore — status refresh will reflect reality */ }
  }

  async function handleConnectOnedrive() {
    setOdConnecting(true)
    setOdConnectError("")
    try {
      await connectOnedrive()             // opens the browser, resolves when logged in
      const status = await getOnedriveStatus()
      setOdStatus(status)
      setOdPath(status.path ?? "")
    } catch (e) {
      setOdConnectError(e instanceof Error ? e.message : "OneDrive login failed")
    } finally {
      setOdConnecting(false)
    }
  }

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
        odEnabled && odStatus?.configured === true,
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
            marginBottom: "16px",
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

        {/* OneDrive section */}
        <div
          style={{
            marginBottom: "20px",
            borderRadius: "8px",
            border: "1px solid #1a2840",
            overflow: "hidden",
          }}
        >
          {/* Header row */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 12px",
              background: "#0a1628",
              cursor: "pointer",
              userSelect: "none",
            }}
            onClick={() => { if (!scanning) setOdExpanded((v) => !v) }}
          >
            <Cloud size={14} style={{ color: "#4a6080", flexShrink: 0 }} />
            <span style={{ fontSize: "0.8125rem", color: "#94a3b8", flex: 1 }}>
              Cloud sources
            </span>
            {odStatus?.configured && (
              <span style={{ fontSize: "0.75rem", color: "#10b981", marginRight: "4px" }}>
                OneDrive: {odStatus.remote}
              </span>
            )}
            {odExpanded
              ? <ChevronUp size={14} style={{ color: "#4a6080" }} />
              : <ChevronDown size={14} style={{ color: "#4a6080" }} />}
          </div>

          {/* Expanded body */}
          {odExpanded && (
            <div style={{ padding: "12px", background: "#080e1a", borderTop: "1px solid #1a2840" }}>

              {/* rclone not installed */}
              {odStatus && !odStatus.rclone_installed && (
                <div style={{ fontSize: "0.75rem", color: "#94a3b8", lineHeight: 1.6 }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "6px", color: "#f59e0b", marginBottom: "6px" }}>
                    <AlertCircle size={13} style={{ flexShrink: 0, marginTop: "2px" }} />
                    <span>OneDrive uses <b>rclone</b>, which isn&apos;t installed.</span>
                  </div>
                  <div style={{ background: "#0d1625", border: "1px solid #1a2840", borderRadius: "6px", padding: "8px 10px", fontFamily: "ui-monospace, Menlo, monospace", color: "#cbd5e1" }}>
                    brew install rclone<br />rclone config&nbsp;&nbsp;<span style={{ color: "#4a6080" }}># create a remote named &quot;onedrive&quot;</span>
                  </div>
                </div>
              )}

              {/* rclone available but no onedrive remote → one-click connect */}
              {odStatus && odStatus.rclone_installed && odStatus.remotes.length === 0 && (
                <div style={{ fontSize: "0.75rem", color: "#94a3b8", lineHeight: 1.6 }}>
                  <p style={{ margin: "0 0 8px 0" }}>
                    Connect your OneDrive to check and back up photos.
                    <span style={{ color: "#4a6080" }}> No Azure app needed — a browser login opens.</span>
                  </p>
                  <button
                    onClick={handleConnectOnedrive}
                    disabled={odConnecting}
                    style={{
                      width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: "6px",
                      background: odConnecting ? "#1e3a5f" : "#0369a1", border: "none", borderRadius: "8px",
                      padding: "8px 12px", fontSize: "0.8125rem", fontWeight: 500,
                      color: "#fff", cursor: odConnecting ? "default" : "pointer",
                    }}
                  >
                    {odConnecting
                      ? <><Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> Waiting for browser login…</>
                      : <>Connect OneDrive</>}
                  </button>
                  {odConnectError && (
                    <p style={{ margin: "6px 0 0 0", color: "#f43f5e" }}>{odConnectError}</p>
                  )}
                </div>
              )}

              {/* Remote(s) available — toggle + picker */}
              {odStatus && odStatus.remotes.length > 0 && (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                    <div
                      style={{
                        width: "16px", height: "16px", borderRadius: "4px", flexShrink: 0,
                        border: `1px solid ${odEnabled && odStatus.configured ? "#3b82f6" : "#1a2840"}`,
                        background: odEnabled && odStatus.configured ? "#3b82f6" : "#080e1a",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        cursor: (!scanning && odStatus.configured) ? "pointer" : "not-allowed",
                        opacity: odStatus.configured ? 1 : 0.4,
                        transition: "background 150ms, border-color 150ms",
                      }}
                      onClick={() => { if (!scanning && odStatus.configured) setOdEnabled((v) => !v) }}
                    >
                      {odEnabled && odStatus.configured && (
                        <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                          <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </div>
                    <span style={{ fontSize: "0.875rem", color: "#cbd5e1", flex: 1 }}>
                      Check against OneDrive
                    </span>
                    {/* Remote picker (only if more than one) */}
                    {odStatus.remotes.length > 1 && (
                      <select
                        value={odStatus.remote ?? ""}
                        disabled={scanning}
                        onChange={(e) => persistOnedrive(e.target.value, odPath)}
                        style={{
                          background: "#0d1625", border: "1px solid #1a2840", borderRadius: "6px",
                          padding: "4px 8px", fontSize: "0.75rem", color: "#e2e8f0", outline: "none",
                        }}
                      >
                        <option value="" disabled>choose remote…</option>
                        {odStatus.remotes.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    )}
                  </div>

                  {/* Optional subfolder — greatly speeds up indexing on large drives */}
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "0.75rem", color: "#4a6080", flexShrink: 0, fontFamily: "ui-monospace, Menlo, monospace" }}>
                      {odStatus.remote ?? "onedrive"}:
                    </span>
                    <input
                      type="text"
                      value={odPath}
                      disabled={scanning || !odStatus.remote}
                      placeholder="Images  (optional folder — faster)"
                      onChange={(e) => setOdPath(e.target.value)}
                      onBlur={() => { if (odStatus.remote && odPath !== (odStatus.path ?? "")) persistOnedrive(odStatus.remote, odPath) }}
                      style={{
                        flex: 1, background: "#0d1625", border: "1px solid #1a2840", borderRadius: "6px",
                        padding: "5px 8px", fontSize: "0.75rem", color: "#e2e8f0", outline: "none",
                        fontFamily: "ui-monospace, Menlo, monospace",
                      }}
                      onFocus={(e) => { e.currentTarget.style.borderColor = "#3b82f6" }}
                    />
                  </div>

                  {odEnabled && odStatus.configured && (
                    <p style={{ margin: 0, fontSize: "0.75rem", color: "#f59e0b", lineHeight: 1.5 }}>
                      ⚠ First scan indexes {odPath ? `"${odPath}"` : "your whole OneDrive"} (can take minutes for large drives). Cached 24h afterwards.
                    </p>
                  )}
                </>
              )}

            </div>
          )}
        </div>

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
