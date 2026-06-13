"use client"

import { useState } from "react"
import { X, SlidersHorizontal } from "lucide-react"
import type { AdvancedFilters } from "@/lib/types"
import { DEFAULT_ADVANCED_FILTERS } from "@/lib/types"

interface Props {
  filters: AdvancedFilters
  onChange: (f: AdvancedFilters) => void
  onClose: () => void
}

function Section({ title }: { title: string }) {
  return (
    <p className="text-xs uppercase tracking-wider mb-2" style={{ color: "#4a6080" }}>
      {title}
    </p>
  )
}

type RadioOption<T extends string> = { value: T; label: string }

function RadioGroup<T extends string>({
  options,
  value,
  onChange,
}: {
  options: RadioOption<T>[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="flex gap-1 flex-wrap">
      {options.map((opt) => {
        const active = value === opt.value
        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            className="h-6 px-2.5 rounded-full text-xs font-medium border transition-colors duration-150"
            style={
              active
                ? { background: "#1a3a5c", borderColor: "#3b82f6", color: "#60a5fa" }
                : { background: "transparent", borderColor: "#1a2840", color: "#4a6080" }
            }
            onMouseEnter={(e) => {
              if (!active) e.currentTarget.style.color = "#94a3b8"
            }}
            onMouseLeave={(e) => {
              if (!active) e.currentTarget.style.color = "#4a6080"
            }}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

export default function AdvancedFilterModal({ filters, onChange, onClose }: Props) {
  const [draft, setDraft] = useState<AdvancedFilters>({ ...filters })

  function set<K extends keyof AdvancedFilters>(key: K, value: AdvancedFilters[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }))
  }

  function handleApply() {
    onChange(draft)
    onClose()
  }

  function handleReset() {
    setDraft({ ...DEFAULT_ADVANCED_FILTERS })
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.6)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-[360px] rounded-xl shadow-2xl flex flex-col overflow-hidden"
        style={{ background: "#0d1625", border: "1px solid #1a2840" }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-2 px-4 py-3 shrink-0"
          style={{ borderBottom: "1px solid #1a2840" }}
        >
          <SlidersHorizontal size={14} style={{ color: "#60a5fa" }} />
          <span className="flex-1 text-sm font-semibold" style={{ color: "#e2e8f0" }}>
            Advanced filters
          </span>
          <button
            onClick={onClose}
            className="rounded p-1 transition-colors duration-150"
            style={{ color: "#4a6080" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#e2e8f0")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#4a6080")}
          >
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="px-4 py-3 flex flex-col gap-4 overflow-y-auto" style={{ maxHeight: "70vh" }}>

          {/* Date range */}
          <div>
            <Section title="Date taken" />
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={draft.dateFrom ?? ""}
                onChange={(e) => set("dateFrom", e.target.value || null)}
                className="flex-1 rounded-md px-2 py-1 text-xs outline-none"
                style={{ background: "#111d30", border: "1px solid #1a2840", color: "#e2e8f0", colorScheme: "dark" }}
              />
              <span className="text-xs" style={{ color: "#4a6080" }}>to</span>
              <input
                type="date"
                value={draft.dateTo ?? ""}
                onChange={(e) => set("dateTo", e.target.value || null)}
                className="flex-1 rounded-md px-2 py-1 text-xs outline-none"
                style={{ background: "#111d30", border: "1px solid #1a2840", color: "#e2e8f0", colorScheme: "dark" }}
              />
            </div>
            <p className="mt-1.5 text-xs" style={{ color: "#4a6080" }}>
              Requires a new scan — older results may not have EXIF dates.
            </p>
          </div>

          {/* GPS */}
          <div>
            <Section title="GPS location" />
            <RadioGroup
              value={draft.gps}
              onChange={(v) => set("gps", v)}
              options={[
                { value: "all", label: "All" },
                { value: "with", label: "With GPS" },
                { value: "without", label: "Without GPS" },
              ]}
            />
          </div>

          {/* Camera */}
          <div>
            <Section title="Camera info" />
            <RadioGroup
              value={draft.camera}
              onChange={(v) => set("camera", v)}
              options={[
                { value: "all", label: "All" },
                { value: "with", label: "With camera tag" },
                { value: "without", label: "Without camera tag" },
              ]}
            />
          </div>

          {/* Size */}
          <div>
            <Section title="File size" />
            <RadioGroup
              value={draft.sizeRange}
              onChange={(v) => set("sizeRange", v)}
              options={[
                { value: "all", label: "All" },
                { value: "xs", label: "< 500 KB" },
                { value: "sm", label: "500 KB – 5 MB" },
                { value: "md", label: "5 – 25 MB" },
                { value: "lg", label: "> 25 MB" },
              ]}
            />
          </div>

          {/* Resolution */}
          <div>
            <Section title="Resolution" />
            <RadioGroup
              value={draft.resolution}
              onChange={(v) => set("resolution", v)}
              options={[
                { value: "all", label: "All" },
                { value: "low", label: "< 2 MP" },
                { value: "hd", label: "2 – 8 MP" },
                { value: "4k", label: "> 8 MP" },
              ]}
            />
          </div>
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between px-4 py-3 shrink-0"
          style={{ borderTop: "1px solid #1a2840" }}
        >
          <button
            onClick={handleReset}
            className="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors duration-150"
            style={{ background: "transparent", color: "#4a6080", border: "1px solid #1a2840" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#94a3b8")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#4a6080")}
          >
            Reset
          </button>
          <button
            onClick={handleApply}
            className="rounded-lg px-4 py-1.5 text-xs font-semibold transition-colors duration-150"
            style={{ background: "#1a3a5c", color: "#60a5fa", border: "1px solid #3b82f6" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#1e4570")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "#1a3a5c")}
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  )
}
