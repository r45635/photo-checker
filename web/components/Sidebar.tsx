"use client"

import {
  Camera,
  ScanLine,
  RefreshCw,
  ExternalLink,
  Search,
  X,
  Folder,
  FolderOpen,
  ChevronUp,
  ChevronDown,
} from "lucide-react"
import type { FilterStatus, ResultFile, SortBy } from "@/lib/types"

interface SidebarProps {
  results: ResultFile[]
  selectedSlug: string | null
  onSelectSlug: (slug: string) => void
  filterStatus: FilterStatus
  onFilterStatus: (s: FilterStatus) => void
  search: string
  onSearch: (s: string) => void
  sortBy: SortBy
  onSortBy: (s: SortBy) => void
  sortDesc: boolean
  onSortDesc: (v: boolean) => void
  subfolders: Map<string, number>
  selectedSubfolder: string | null
  onSelectSubfolder: (sf: string | null) => void
  onScanClick: () => void
  onRescan: () => void
  onOpenFinder: () => void
  stats: { total: number; yes: number; no: number; maybe: number; yesMB: number }
}

function depthOf(path: string): number {
  return path.split("/").filter(Boolean).length - 1
}

function lastSegment(path: string): string {
  const parts = path.split("/").filter(Boolean)
  return parts[parts.length - 1] ?? path
}

export default function Sidebar({
  results,
  selectedSlug,
  onSelectSlug,
  filterStatus,
  onFilterStatus,
  search,
  onSearch,
  sortBy,
  onSortBy,
  sortDesc,
  onSortDesc,
  subfolders,
  selectedSubfolder,
  onSelectSubfolder,
  onScanClick,
  onRescan,
  onOpenFinder,
  stats,
}: SidebarProps) {
  const sortOptions: { key: SortBy; label: string }[] = [
    { key: "name", label: "Name" },
    { key: "date", label: "Date" },
    { key: "subfolder", label: "Folder" },
  ]

  const filterOptions: { key: FilterStatus; label: string; color: string; activeClass: string }[] = [
    {
      key: "ALL",
      label: "All",
      color: "",
      activeClass: "bg-blue-600 text-white border-blue-600",
    },
    {
      key: "YES",
      label: "YES",
      color: "",
      activeClass: "bg-emerald-600 text-white border-emerald-600",
    },
    {
      key: "NO",
      label: "NO",
      color: "",
      activeClass: "bg-rose-600 text-white border-rose-600",
    },
    {
      key: "MAYBE",
      label: "MAYBE",
      color: "",
      activeClass: "bg-amber-500 text-white border-amber-500",
    },
  ]

  const hasSubfolders =
    subfolders.size > 0 &&
    Array.from(subfolders.keys()).some((k) => k !== "")

  const sortedSubfolders = Array.from(subfolders.entries())
    .filter(([k]) => k !== "")
    .sort(([a], [b]) => a.localeCompare(b))

  return (
    <aside
      className="fixed left-0 top-0 h-screen w-[260px] flex flex-col"
      style={{
        background: "#080e1a",
        borderRight: "1px solid #1a2840",
      }}
    >
      {/* ── Header ── */}
      <div
        className="px-4 py-4"
        style={{ borderBottom: "1px solid #1a2840" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Camera size={20} className="text-blue-400 shrink-0" />
          <span className="font-semibold text-slate-200 text-sm leading-none">
            Photo Checker
          </span>
        </div>

        {/* Stats pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span
            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
            style={{ background: "rgba(16,185,129,0.15)", color: "#10b981" }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
            {stats.yes}
          </span>
          <span
            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
            style={{ background: "rgba(244,63,94,0.15)", color: "#f43f5e" }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-rose-400 inline-block" />
            {stats.no}
          </span>
          <span
            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
            style={{ background: "rgba(245,158,11,0.15)", color: "#f59e0b" }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
            {stats.maybe}
          </span>
          {stats.total > 0 && (
            <span
              className="text-xs ml-auto"
              style={{ color: "#4a6080" }}
            >
              {stats.total} total
            </span>
          )}
        </div>
      </div>

      {/* ── Scan buttons ── */}
      <div className="px-3 pt-3 pb-2 space-y-2">
        <button
          onClick={onScanClick}
          className="w-full flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-white transition-colors duration-150"
          style={{ background: "#3b82f6" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "#60a5fa")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "#3b82f6")}
        >
          <ScanLine size={15} />
          Scan folder
        </button>

        {selectedSlug && (
          <div className="flex gap-1.5">
            <button
              onClick={onRescan}
              className="flex-1 flex items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-slate-400 transition-colors duration-150"
              style={{ border: "1px solid #1a2840" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#e2e8f0")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#94a3b8")}
            >
              <RefreshCw size={12} />
              Re-scan
            </button>
            <button
              onClick={onOpenFinder}
              className="flex-1 flex items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-slate-400 transition-colors duration-150"
              style={{ border: "1px solid #1a2840" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#e2e8f0")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#94a3b8")}
            >
              <ExternalLink size={12} />
              Finder
            </button>
          </div>
        )}
      </div>

      {/* ── Result file picker ── */}
      {results.length > 0 && (
        <div className="px-3 py-2">
          <p
            className="text-xs uppercase tracking-wider mb-1.5"
            style={{ color: "#4a6080" }}
          >
            Results
          </p>
          <div className="space-y-0.5">
            {results.map((r) => {
              const active = r.slug === selectedSlug
              return (
                <button
                  key={r.slug}
                  onClick={() => onSelectSlug(r.slug)}
                  className="w-full flex items-center justify-between rounded-md px-2 py-1.5 text-sm text-left transition-colors duration-150"
                  style={{
                    background: active ? "rgba(59,130,246,0.1)" : "transparent",
                    color: active ? "#60a5fa" : "#94a3b8",
                  }}
                  onMouseEnter={(e) => {
                    if (!active) e.currentTarget.style.color = "#e2e8f0"
                  }}
                  onMouseLeave={(e) => {
                    if (!active) e.currentTarget.style.color = "#94a3b8"
                  }}
                >
                  <span className="truncate">{r.name}</span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Divider ── */}
      <div style={{ height: "1px", background: "#1a2840", margin: "0 12px" }} />

      {/* ── Filter pills ── */}
      <div className="px-3 py-2">
        <p
          className="text-xs uppercase tracking-wider mb-1.5"
          style={{ color: "#4a6080" }}
        >
          Filter
        </p>
        <div className="flex gap-1 flex-wrap">
          {filterOptions.map((opt) => {
            const active = filterStatus === opt.key
            return (
              <button
                key={opt.key}
                onClick={() => onFilterStatus(opt.key)}
                className={`h-6 px-2 rounded-full text-xs font-medium border transition-colors duration-150 ${
                  active ? opt.activeClass : "text-slate-500"
                }`}
                style={
                  !active
                    ? { borderColor: "#1a2840", background: "transparent" }
                    : {}
                }
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Search ── */}
      <div className="px-3 py-2">
        <div
          className="flex items-center gap-2 rounded-lg px-2.5 py-1.5"
          style={{ background: "#0d1625", border: "1px solid #1a2840" }}
        >
          <Search size={13} style={{ color: "#4a6080" }} className="shrink-0" />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search filename…"
            className="flex-1 bg-transparent text-sm outline-none min-w-0"
            style={{ color: "#e2e8f0" }}
          />
          {search && (
            <button
              onClick={() => onSearch("")}
              className="shrink-0 transition-colors duration-150"
              style={{ color: "#4a6080" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#e2e8f0")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#4a6080")}
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* ── Sort controls ── */}
      <div className="px-3 py-2">
        <p
          className="text-xs uppercase tracking-wider mb-1.5"
          style={{ color: "#4a6080" }}
        >
          Sort
        </p>
        <div className="flex items-center gap-1">
          <div className="flex gap-0.5 flex-1">
            {sortOptions.map((opt) => {
              const active = sortBy === opt.key
              return (
                <button
                  key={opt.key}
                  onClick={() => onSortBy(opt.key)}
                  className="flex-1 rounded-md px-1.5 py-1 text-xs font-medium transition-colors duration-150"
                  style={{
                    background: active ? "#111d30" : "transparent",
                    color: active ? "#e2e8f0" : "#4a6080",
                  }}
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

          <button
            onClick={() => onSortDesc(!sortDesc)}
            className="rounded-md p-1 transition-colors duration-150"
            style={{
              background: "#111d30",
              color: "#94a3b8",
            }}
            title={sortDesc ? "Descending" : "Ascending"}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#e2e8f0")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#94a3b8")}
          >
            {sortDesc ? <ChevronDown size={13} /> : <ChevronUp size={13} />}
          </button>
        </div>
      </div>

      {/* ── Folder tree ── */}
      {hasSubfolders && (
        <>
          <div style={{ height: "1px", background: "#1a2840", margin: "0 12px" }} />

          <div className="px-3 py-2 flex-1 overflow-y-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "#1a2840 transparent" }}>
            <p
              className="text-xs uppercase tracking-wider mb-1.5"
              style={{ color: "#4a6080" }}
            >
              Folders
            </p>

            {/* All folders */}
            <button
              onClick={() => onSelectSubfolder(null)}
              className="w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-left transition-colors duration-150"
              style={{
                background:
                  selectedSubfolder === null
                    ? "rgba(59,130,246,0.08)"
                    : "transparent",
                color:
                  selectedSubfolder === null ? "#60a5fa" : "#94a3b8",
              }}
              onMouseEnter={(e) => {
                if (selectedSubfolder !== null)
                  e.currentTarget.style.color = "#e2e8f0"
              }}
              onMouseLeave={(e) => {
                if (selectedSubfolder !== null)
                  e.currentTarget.style.color = "#94a3b8"
              }}
            >
              <Folder size={13} className="shrink-0" />
              <span className="flex-1 text-xs">All folders</span>
              {subfolders.size > 0 && (
                <span
                  className="rounded px-1 text-xs"
                  style={{ background: "#1a2840", color: "#4a6080" }}
                >
                  {Array.from(subfolders.values()).reduce((a, b) => a + b, 0)}
                </span>
              )}
            </button>

            {/* Subfolder rows */}
            {sortedSubfolders.map(([path, count]) => {
              const depth = depthOf(path)
              const active = selectedSubfolder === path
              return (
                <button
                  key={path}
                  onClick={() => onSelectSubfolder(path)}
                  className="w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-left transition-colors duration-150"
                  style={{
                    paddingLeft: `${8 + depth * 12}px`,
                    background: active ? "rgba(59,130,246,0.08)" : "transparent",
                    color: active ? "#60a5fa" : "#94a3b8",
                  }}
                  onMouseEnter={(e) => {
                    if (!active) e.currentTarget.style.color = "#e2e8f0"
                  }}
                  onMouseLeave={(e) => {
                    if (!active) e.currentTarget.style.color = "#94a3b8"
                  }}
                >
                  {active ? (
                    <FolderOpen size={13} className="shrink-0" />
                  ) : (
                    <Folder size={13} className="shrink-0" />
                  )}
                  <span className="flex-1 text-xs truncate">
                    {lastSegment(path)}
                  </span>
                  <span
                    className="rounded px-1 text-xs shrink-0"
                    style={{ background: "#1a2840", color: "#4a6080" }}
                  >
                    {count}
                  </span>
                </button>
              )
            })}
          </div>
        </>
      )}
    </aside>
  )
}
