"use client"

import { useState } from "react"
import {
  Camera,
  ScanLine,
  Search,
  X,
  Folder,
  FolderOpen,
  ChevronUp,
  ChevronDown,
  RefreshCw,
  ExternalLink,
  Trash2,
  Info,
  ScrollText,
  SlidersHorizontal,
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
  groupByFolder: boolean
  onGroupByFolder: (v: boolean) => void
  subfolders: Map<string, number>
  selectedSubfolder: string | null
  onSelectSubfolder: (sf: string | null) => void
  onScanClick: () => void
  onRescanResult: (slug: string, folder: string) => void
  onOpenFinderResult: (folder: string) => void
  onDeleteResult: (slug: string) => void
  onShowLogs: () => void
  onOpenAdvFilters: () => void
  activeAdvFilterCount: number
  stats: { total: number; yes: number; no: number; maybe: number; yesMB: number }
}

function depthOf(path: string): number {
  return path.split("/").filter(Boolean).length - 1
}

function lastSegment(path: string | undefined | null): string {
  if (!path) return ""
  const parts = path.split("/").filter(Boolean)
  return parts[parts.length - 1] ?? ""
}

function formatDate(ts: number): string {
  return new Date(ts * 1000).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function formatIso(iso: string): string {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return iso
  }
}

function InfoModal({ result, onClose }: { result: ResultFile; onClose: () => void }) {
  const folderName = lastSegment(result.folder) || result.name

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.55)" }}
      onClick={onClose}
    >
      <div
        className="rounded-xl shadow-2xl p-5 w-80 max-w-[90vw]"
        style={{ background: "#0d1625", border: "1px solid #1a2840", color: "#e2e8f0" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-2 min-w-0">
            <Folder size={16} className="text-blue-400 shrink-0 mt-0.5" />
            <span className="font-semibold text-sm leading-snug break-all">{folderName}</span>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-md p-0.5 transition-colors"
            style={{ color: "#4a6080" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#e2e8f0")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#4a6080")}
          >
            <X size={15} />
          </button>
        </div>

        {/* Path */}
        <div className="mb-3">
          <p className="text-xs uppercase tracking-wider mb-1" style={{ color: "#4a6080" }}>Path</p>
          <p className="text-xs break-all leading-relaxed" style={{ color: "#94a3b8" }}>{result.folder || "—"}</p>
        </div>

        {/* Date */}
        <div className="mb-4">
          <p className="text-xs uppercase tracking-wider mb-1" style={{ color: "#4a6080" }}>Scanned</p>
          <p className="text-xs" style={{ color: "#94a3b8" }}>
            {result.scan_date ? formatIso(result.scan_date) : result.mtime ? formatDate(result.mtime) : "—"}
          </p>
        </div>

        {/* Stats */}
        <div style={{ borderTop: "1px solid #1a2840", paddingTop: "12px" }}>
          <p className="text-xs uppercase tracking-wider mb-2" style={{ color: "#4a6080" }}>Results</p>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs" style={{ color: "#10b981" }}>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
                Safe to delete
              </span>
              <span className="text-xs font-medium" style={{ color: "#10b981" }}>
                {result.yes}
                {result.size_yes_mb > 0 && (
                  <span className="ml-1 font-normal" style={{ color: "#4a6080" }}>
                    ({result.size_yes_mb >= 1024
                      ? `${(result.size_yes_mb / 1024).toFixed(1)} GB`
                      : `${result.size_yes_mb} MB`})
                  </span>
                )}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs" style={{ color: "#f43f5e" }}>
                <span className="w-1.5 h-1.5 rounded-full bg-rose-400 inline-block" />
                Not found
              </span>
              <span className="text-xs font-medium" style={{ color: "#f43f5e" }}>{result.no}</span>
            </div>
            {result.maybe > 0 && (
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-xs" style={{ color: "#f59e0b" }}>
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
                  Uncertain
                </span>
                <span className="text-xs font-medium" style={{ color: "#f59e0b" }}>{result.maybe}</span>
              </div>
            )}
            <div className="flex items-center justify-between" style={{ borderTop: "1px solid #1a2840", paddingTop: "6px", marginTop: "4px" }}>
              <span className="text-xs" style={{ color: "#4a6080" }}>Total</span>
              <span className="text-xs font-medium" style={{ color: "#94a3b8" }}>{result.total}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
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
  groupByFolder,
  onGroupByFolder,
  subfolders,
  selectedSubfolder,
  onSelectSubfolder,
  onScanClick,
  onRescanResult,
  onOpenFinderResult,
  onDeleteResult,
  onShowLogs,
  onOpenAdvFilters,
  activeAdvFilterCount,
  stats,
}: SidebarProps) {
  const [infoResult, setInfoResult] = useState<ResultFile | null>(null)

  const sortOptions: { key: SortBy; label: string }[] = [
    { key: "name", label: "Name" },
    { key: "date", label: "Date" },
    { key: "size", label: "Size" },
    { key: "type", label: "Type" },
  ]

  const filterOptions: { key: FilterStatus; label: string; activeClass: string }[] = [
    { key: "ALL",   label: "All",   activeClass: "bg-blue-600 text-white border-blue-600" },
    { key: "YES",   label: "YES",   activeClass: "bg-emerald-600 text-white border-emerald-600" },
    { key: "NO",    label: "NO",    activeClass: "bg-rose-600 text-white border-rose-600" },
    { key: "MAYBE", label: "MAYBE", activeClass: "bg-amber-500 text-white border-amber-500" },
  ]

  const hasSubfolders =
    subfolders.size > 0 && Array.from(subfolders.keys()).some((k) => k !== "")

  const sortedSubfolders = Array.from(subfolders.entries())
    .filter(([k]) => k !== "")
    .sort(([a], [b]) => a.localeCompare(b))

  return (
    <>
      <aside
        className="fixed left-0 top-0 h-screen w-[260px] flex flex-col"
        style={{ background: "#080e1a", borderRight: "1px solid #1a2840" }}
      >
        {/* ── Header ── */}
        <div className="px-4 py-4" style={{ borderBottom: "1px solid #1a2840" }}>
          <div className="flex items-center gap-2 mb-3">
            <Camera size={20} className="text-blue-400 shrink-0" />
            <span className="font-semibold text-slate-200 text-sm leading-none">Photo Checker</span>
          </div>
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
              <span className="text-xs ml-auto" style={{ color: "#4a6080" }}>
                {stats.total} total
              </span>
            )}
          </div>
        </div>

        {/* ── Scan button ── */}
        <div className="px-3 pt-3 pb-2">
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
        </div>

        {/* ── Result file list ── */}
        {results.length > 0 && (
          <div className="px-3 py-2">
            <p className="text-xs uppercase tracking-wider mb-1.5" style={{ color: "#4a6080" }}>
              Results
            </p>
            <div className="space-y-0.5">
              {results.map((r) => {
                const active = r.slug === selectedSlug
                const displayName = lastSegment(r.folder) || r.name
                const isDuplicate = results.filter(
                  (x) => (lastSegment(x.folder) || x.name) === displayName
                ).length > 1
                return (
                  <div
                    key={r.slug}
                    className="group/result flex items-center rounded-md transition-colors duration-150"
                    style={{
                      background: active ? "rgba(59,130,246,0.1)" : "transparent",
                    }}
                  >
                    {/* Name — clickable */}
                    <button
                      onClick={() => onSelectSlug(r.slug)}
                      className="flex-1 text-left px-2 py-1 min-w-0"
                      style={{ color: active ? "#60a5fa" : "#94a3b8" }}
                      onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = "#e2e8f0" }}
                      onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = "#94a3b8" }}
                    >
                      <p className="text-sm truncate">{displayName}</p>
                      {(isDuplicate || r.scan_date) && (
                        <p className="text-xs truncate" style={{ color: "#4a6080" }}>
                          {isDuplicate ? r.folder : r.scan_date ? formatIso(r.scan_date) : ""}
                        </p>
                      )}
                    </button>

                    {/* Action icons — visible on row hover */}
                    <div className="flex items-center gap-0 pr-1 opacity-0 group-hover/result:opacity-100 transition-opacity duration-150 shrink-0">
                      <ActionIcon
                        title="Info"
                        onClick={() => setInfoResult(r)}
                      >
                        <Info size={11} />
                      </ActionIcon>
                      <ActionIcon
                        title="Re-scan"
                        onClick={() => onRescanResult(r.slug, r.folder)}
                      >
                        <RefreshCw size={11} />
                      </ActionIcon>
                      <ActionIcon
                        title="Open in Finder"
                        onClick={() => onOpenFinderResult(r.folder)}
                      >
                        <ExternalLink size={11} />
                      </ActionIcon>
                      <ActionIcon
                        title="Delete result"
                        danger
                        onClick={() => onDeleteResult(r.slug)}
                      >
                        <Trash2 size={11} />
                      </ActionIcon>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* ── Divider ── */}
        <div style={{ height: "1px", background: "#1a2840", margin: "0 12px" }} />

        {/* ── Filter pills ── */}
        <div className="px-3 py-2">
          <p className="text-xs uppercase tracking-wider mb-1.5" style={{ color: "#4a6080" }}>Filter</p>
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
                  style={!active ? { borderColor: "#1a2840", background: "transparent" } : {}}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
          <button
            onClick={onOpenAdvFilters}
            className="mt-2 w-full flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors duration-150"
            style={{
              background: activeAdvFilterCount > 0 ? "#1a3a5c" : "transparent",
              color: activeAdvFilterCount > 0 ? "#60a5fa" : "#4a6080",
              border: `1px solid ${activeAdvFilterCount > 0 ? "#3b82f6" : "#1a2840"}`,
            }}
            onMouseEnter={(e) => { if (activeAdvFilterCount === 0) e.currentTarget.style.color = "#94a3b8" }}
            onMouseLeave={(e) => { if (activeAdvFilterCount === 0) e.currentTarget.style.color = "#4a6080" }}
          >
            <SlidersHorizontal size={11} />
            <span className="flex-1 text-left">Advanced filters</span>
            {activeAdvFilterCount > 0 && (
              <span
                className="rounded-full px-1.5 text-[10px] font-semibold"
                style={{ background: "#3b82f6", color: "#fff" }}
              >
                {activeAdvFilterCount}
              </span>
            )}
          </button>
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
          <p className="text-xs uppercase tracking-wider mb-1.5" style={{ color: "#4a6080" }}>Sort</p>
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
                    onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = "#94a3b8" }}
                    onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = "#4a6080" }}
                  >
                    {opt.label}
                  </button>
                )
              })}
            </div>
            <button
              onClick={() => onGroupByFolder(!groupByFolder)}
              className="rounded-md p-1 transition-colors duration-150"
              style={{
                background: groupByFolder ? "#1a3a5c" : "#111d30",
                color: groupByFolder ? "#60a5fa" : "#4a6080",
              }}
              title={groupByFolder ? "Grouped by folder — click to disable" : "Group by folder"}
              onMouseEnter={(e) => { if (!groupByFolder) e.currentTarget.style.color = "#94a3b8" }}
              onMouseLeave={(e) => { if (!groupByFolder) e.currentTarget.style.color = "#4a6080" }}
            >
              <Folder size={13} />
            </button>
            <button
              onClick={() => onSortDesc(!sortDesc)}
              className="rounded-md p-1 transition-colors duration-150"
              style={{ background: "#111d30", color: "#94a3b8" }}
              title={sortDesc ? "Descending — click for ascending" : "Ascending — click for descending"}
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
            <div
              className="px-3 py-2 flex-1 overflow-y-auto"
              style={{ scrollbarWidth: "thin", scrollbarColor: "#1a2840 transparent" }}
            >
              <p className="text-xs uppercase tracking-wider mb-1.5" style={{ color: "#4a6080" }}>Folders</p>

              <button
                onClick={() => onSelectSubfolder(null)}
                className="w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-left transition-colors duration-150"
                style={{
                  background: selectedSubfolder === null ? "rgba(59,130,246,0.08)" : "transparent",
                  color: selectedSubfolder === null ? "#60a5fa" : "#94a3b8",
                }}
                onMouseEnter={(e) => { if (selectedSubfolder !== null) e.currentTarget.style.color = "#e2e8f0" }}
                onMouseLeave={(e) => { if (selectedSubfolder !== null) e.currentTarget.style.color = "#94a3b8" }}
              >
                <Folder size={13} className="shrink-0" />
                <span className="flex-1 text-xs">All folders</span>
                {subfolders.size > 0 && (
                  <span className="rounded px-1 text-xs" style={{ background: "#1a2840", color: "#4a6080" }}>
                    {Array.from(subfolders.values()).reduce((a, b) => a + b, 0)}
                  </span>
                )}
              </button>

              {sortedSubfolders.map(([path, count]) => {
                const depth = depthOf(path)
                const active = selectedSubfolder === path
                return (
                  <button
                    key={path}
                    onClick={() => onSelectSubfolder(path)}
                    className="w-full flex items-center gap-2 rounded-md py-1.5 text-sm text-left transition-colors duration-150"
                    style={{
                      paddingLeft: `${8 + depth * 12}px`,
                      background: active ? "rgba(59,130,246,0.08)" : "transparent",
                      color: active ? "#60a5fa" : "#94a3b8",
                    }}
                    onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = "#e2e8f0" }}
                    onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = "#94a3b8" }}
                  >
                    {active ? <FolderOpen size={13} className="shrink-0" /> : <Folder size={13} className="shrink-0" />}
                    <span className="flex-1 text-xs truncate">{lastSegment(path)}</span>
                    <span className="rounded px-1 text-xs shrink-0" style={{ background: "#1a2840", color: "#4a6080" }}>
                      {count}
                    </span>
                  </button>
                )
              })}
            </div>
          </>
        )}
        {/* ── Logs button ── */}
        <div className="px-3 pb-3 mt-auto shrink-0">
          <button
            onClick={onShowLogs}
            className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors duration-150"
            style={{ color: "#4a6080", background: "transparent" }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "#94a3b8"; e.currentTarget.style.background = "#0d1625" }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "#4a6080"; e.currentTarget.style.background = "transparent" }}
          >
            <ScrollText size={13} />
            Server logs
          </button>
        </div>
      </aside>

      {/* ── Info modal ── */}
      {infoResult && <InfoModal result={infoResult} onClose={() => setInfoResult(null)} />}
    </>
  )
}

function ActionIcon({
  children,
  title,
  danger = false,
  onClick,
}: {
  children: React.ReactNode
  title: string
  danger?: boolean
  onClick: () => void
}) {
  return (
    <button
      title={title}
      onClick={(e) => { e.stopPropagation(); onClick() }}
      className="rounded p-1 transition-colors duration-100"
      style={{ color: "#4a6080" }}
      onMouseEnter={(e) =>
        (e.currentTarget.style.color = danger ? "#f43f5e" : "#e2e8f0")
      }
      onMouseLeave={(e) => (e.currentTarget.style.color = "#4a6080")}
    >
      {children}
    </button>
  )
}
