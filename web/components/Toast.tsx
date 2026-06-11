"use client"

import { useEffect } from "react"
import { CheckCircle2, X } from "lucide-react"

interface ToastProps {
  message: string
  onDismiss: () => void
  durationMs?: number
}

export default function Toast({ message, onDismiss, durationMs = 4000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, durationMs)
    return () => clearTimeout(timer)
  }, [onDismiss, durationMs])

  return (
    <div
      className="fixed bottom-20 left-1/2 -translate-x-1/2 z-[200] flex items-center gap-3 rounded-xl border border-[#1a2840] bg-[#0d1625] px-4 py-3 shadow-2xl"
      style={{ minWidth: "240px", maxWidth: "420px" }}
    >
      <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />
      <span className="flex-1 text-sm text-slate-300">{message}</span>
      <button
        onClick={onDismiss}
        className="shrink-0 text-slate-500 hover:text-slate-300 transition-colors duration-150"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  )
}
