"use client"

import { useEffect, useRef, useState } from "react"
import { X, RefreshCw, Terminal } from "lucide-react"

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

interface LogPanelProps {
  onClose: () => void
}

export default function LogPanel({ onClose }: LogPanelProps) {
  const [lines, setLines] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  async function fetchLogs() {
    setLoading(true)
    try {
      const res = await fetch(`${BASE}/api/logs?n=200`)
      if (res.ok) setLines(await res.json())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchLogs() }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [lines])

  function levelColor(line: string): string {
    if (line.includes("] ERROR")) return "#f43f5e"
    if (line.includes("] WARN ")) return "#f59e0b"
    if (line.includes("] INFO ")) return "#60a5fa"
    return "#64748b"
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center pb-6 px-4"
      style={{ background: "rgba(0,0,0,0.6)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl rounded-xl flex flex-col"
        style={{
          background: "#080e1a",
          border: "1px solid #1a2840",
          maxHeight: "70vh",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 shrink-0"
          style={{ borderBottom: "1px solid #1a2840" }}
        >
          <div className="flex items-center gap-2">
            <Terminal size={14} className="text-blue-400" />
            <span className="text-sm font-medium text-slate-200">Server logs</span>
            <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "#111d30", color: "#4a6080" }}>
              last {lines.length} lines
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={fetchLogs}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-[#1a2840] transition-colors"
              title="Refresh"
            >
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-[#1a2840] transition-colors"
            >
              <X size={13} />
            </button>
          </div>
        </div>

        {/* Log lines */}
        <div
          className="flex-1 overflow-y-auto p-4 font-mono text-xs"
          style={{ scrollbarWidth: "thin", scrollbarColor: "#1a2840 transparent" }}
        >
          {lines.length === 0 ? (
            <p className="text-slate-600">No logs yet.</p>
          ) : (
            lines.map((line, i) => (
              <div key={i} style={{ color: levelColor(line), lineHeight: "1.6" }}>
                {line}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
