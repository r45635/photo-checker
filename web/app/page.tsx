"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { Loader2 } from "lucide-react"
import Sidebar from "@/components/Sidebar"
import PhotoCard from "@/components/PhotoCard"
import DetailPanel from "@/components/DetailPanel"
import BatchBar from "@/components/BatchBar"
import ScanDialog from "@/components/ScanDialog"
import Toast from "@/components/Toast"
import { listResults, getResults, deleteResult, thumbnailUrl, openInFinder, scanFolder } from "@/lib/api"
import type { FilterStatus, PhotoRecord, ResultFile, SortBy } from "@/lib/types"

export default function HomePage() {
  // ── Core state ─────────────────────────────────────────────────────────────
  const [results, setResults] = useState<ResultFile[]>([])
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)
  const [records, setRecords] = useState<PhotoRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ── UI state ───────────────────────────────────────────────────────────────
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("YES")
  const [search, setSearch] = useState("")
  const [selectedSubfolder, setSelectedSubfolder] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<SortBy>("date")
  const [sortDesc, setSortDesc] = useState(false)
  const [batch, setBatch] = useState<Set<string>>(new Set())
  const [detail, setDetail] = useState<PhotoRecord | null>(null)
  const [scanOpen, setScanOpen] = useState(false)
  const [rescanLoading, setRescanLoading] = useState(false)
  const [visibleCount, setVisibleCount] = useState(32)
  const [toast, setToast] = useState<string | null>(null)

  // ── Infinite scroll sentinel & shift-click tracking ───────────────────────
  const sentinelRef = useRef<HTMLDivElement>(null)
  const lastSelectedIndex = useRef<number>(-1)

  // ── On mount: load result list ─────────────────────────────────────────────
  useEffect(() => {
    listResults()
      .then((res) => {
        setResults(res)
        if (res.length === 1) {
          setSelectedSlug(res[0].slug)
        }
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load results")
      })
  }, [])

  // ── Load records when selectedSlug changes ─────────────────────────────────
  useEffect(() => {
    if (!selectedSlug) {
      setRecords([])
      return
    }
    setLoading(true)
    setError(null)
    setVisibleCount(32)
    setBatch(new Set())
    setDetail(null)
    setSelectedSubfolder(null)

    getResults(selectedSlug)
      .then((recs) => setRecords(recs))
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load results")
      })
      .finally(() => setLoading(false))
  }, [selectedSlug])

  // ── Derived: pre-subfolder filtered (status + search only) ────────────────
  const preSubfiltered = useMemo<PhotoRecord[]>(() => {
    let list = records
    if (filterStatus !== "ALL") {
      list = list.filter((r) => r.safe_to_delete === filterStatus)
    }
    if (search.trim()) {
      const lower = search.trim().toLowerCase()
      list = list.filter((r) => r.filename.toLowerCase().includes(lower))
    }
    return list
  }, [records, filterStatus, search])

  // ── Derived: subfolderMap (counts reflect current status+search filter) ────
  const subfolderMap = useMemo<Map<string, number>>(() => {
    const m = new Map<string, number>()
    for (const r of preSubfiltered) {
      const sf = r._subfolder ?? ""
      m.set(sf, (m.get(sf) ?? 0) + 1)
    }
    return m
  }, [preSubfiltered])

  // ── Derived: stats ─────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    let yes = 0
    let no = 0
    let maybe = 0
    let yesSizeKb = 0
    for (const r of records) {
      if (r.safe_to_delete === "YES") {
        yes++
        yesSizeKb += r.size_kb
      } else if (r.safe_to_delete === "NO") {
        no++
      } else {
        maybe++
      }
    }
    return {
      total: records.length,
      yes,
      no,
      maybe,
      yesGB: yesSizeKb / 1024 / 1024,
      yesMB: yesSizeKb / 1024,
    }
  }, [records])

  // ── Derived: filtered & sorted ─────────────────────────────────────────────
  const filtered = useMemo<PhotoRecord[]>(() => {
    // Start from pre-subfolder filtered list (status + search already applied)
    let list = preSubfiltered

    // Filter by subfolder
    if (selectedSubfolder !== null) {
      list = list.filter((r) => r._subfolder === selectedSubfolder)
    }

    // Sort
    list = [...list].sort((a, b) => {
      let cmp = 0
      if (sortBy === "name") {
        cmp = a.filename.toLowerCase().localeCompare(b.filename.toLowerCase())
      } else if (sortBy === "date") {
        const extractDate = (r: PhotoRecord) => {
          const m = r.filename.match(/d(\d{8})/)
          return m ? m[1] : r.filename
        }
        cmp = extractDate(a).localeCompare(extractDate(b))
      } else {
        // subfolder
        const sfA = (a._subfolder ?? "") + "\x00" + a.filename.toLowerCase()
        const sfB = (b._subfolder ?? "") + "\x00" + b.filename.toLowerCase()
        cmp = sfA.localeCompare(sfB)
      }
      return sortDesc ? -cmp : cmp
    })

    return list
  }, [preSubfiltered, selectedSubfolder, sortBy, sortDesc])

  // ── Derived: visible slice ─────────────────────────────────────────────────
  const visible = useMemo(() => filtered.slice(0, visibleCount), [filtered, visibleCount])

  // ── Derived: path → index in filtered (for shift-click) ──────────────────
  const filteredIndexMap = useMemo<Map<string, number>>(() => {
    const m = new Map<string, number>()
    filtered.forEach((r, i) => m.set(r.path, i))
    return m
  }, [filtered])

  // ── Reset visibleCount only when filter/sort params change (not on import/delete) ──
  const filterKey = filterStatus + search + (selectedSubfolder ?? "") + sortBy + String(sortDesc)
  const prevFilterKey = useRef(filterKey)
  if (prevFilterKey.current !== filterKey) {
    prevFilterKey.current = filterKey
    setVisibleCount(32)
  }

  // ── Infinite scroll ────────────────────────────────────────────────────────
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && visibleCount < filtered.length) {
          setVisibleCount((c) => c + 32)
        }
      },
      { rootMargin: "400px" }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [visibleCount, filtered.length])

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName
      if (tag === "INPUT" || tag === "TEXTAREA") return

      if (e.key === "Escape") {
        if (detail) { setDetail(null); return }
        if (batch.size > 0) { setBatch(new Set()); return }
      }

      if ((e.metaKey || e.ctrlKey) && e.key === "a") {
        e.preventDefault()
        handleSelectAll()
        return
      }

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault()
        const idx = detail ? (filteredIndexMap.get(detail.path) ?? -1) : -1
        const next = filtered[Math.min(idx + 1, filtered.length - 1)]
        if (next) setDetail(next)
        return
      }

      if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault()
        const idx = detail ? (filteredIndexMap.get(detail.path) ?? 0) : 0
        const prev = filtered[Math.max(idx - 1, 0)]
        if (prev) setDetail(prev)
        return
      }

      if (e.key === " " && detail) {
        e.preventDefault()
        handleSelect(detail.path)
        return
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [detail, filtered, filteredIndexMap, batch])

  // ── Handlers ───────────────────────────────────────────────────────────────
  function handleSelect(path: string) {
    const idx = filteredIndexMap.get(path) ?? -1
    if (idx >= 0) lastSelectedIndex.current = idx
    setBatch((prev) => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }

  function handleShiftSelect(index: number) {
    const anchor = lastSelectedIndex.current
    if (anchor < 0) {
      const r = filtered[index]
      if (r) handleSelect(r.path)
      return
    }
    const start = Math.min(anchor, index)
    const end = Math.max(anchor, index)
    const toAdd = filtered.slice(start, end + 1).map((r) => r.path)
    lastSelectedIndex.current = index
    setBatch((prev) => {
      const next = new Set(prev)
      toAdd.forEach((p) => next.add(p))
      return next
    })
  }

  function handleSelectAll() {
    setBatch(new Set(filtered.map((r) => r.path)))
  }

  function handleView(record: PhotoRecord) {
    setDetail(record)
  }

  function handleClose() {
    setDetail(null)
  }

  function handleImported(path: string) {
    setRecords((prev) =>
      prev.map((r) =>
        r.path === path
          ? { ...r, apple_photos: "yes", safe_to_delete: "YES" }
          : r
      )
    )
    setBatch((prev) => {
      const next = new Set(prev)
      next.delete(path)
      return next
    })
  }

  function handleImportedBatch(paths: string[]) {
    const set = new Set(paths)

    // If the detail panel is showing an imported photo, advance to the next
    // remaining photo so the user keeps their place in the list.
    if (detail && set.has(detail.path)) {
      const currentIdx = filteredIndexMap.get(detail.path) ?? -1
      const nextPhoto =
        filtered.slice(currentIdx + 1).find((r) => !set.has(r.path)) ??
        filtered.slice(0, currentIdx).reverse().find((r) => !set.has(r.path)) ??
        null
      setDetail(nextPhoto)
    }

    setRecords((prev) =>
      prev.map((r) =>
        set.has(r.path)
          ? { ...r, apple_photos: "yes", safe_to_delete: "YES" }
          : r
      )
    )
    setBatch((prev) => {
      const next = new Set(prev)
      paths.forEach((p) => next.delete(p))
      return next
    })
  }

  function handleDeleted(paths: string[], message?: string) {
    const set = new Set(paths)
    setRecords((prev) => prev.filter((r) => !set.has(r.path)))
    setBatch((prev) => {
      const next = new Set(prev)
      paths.forEach((p) => next.delete(p))
      return next
    })
    if (message) setToast(message)
  }

  async function handleScanned(slug: string) {
    setScanOpen(false)
    setLoading(true)
    setError(null)
    try {
      const res = await listResults()
      setResults(res)
      setSelectedSlug(slug)
      const recs = await getResults(slug)
      setRecords(recs)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load scan results")
    } finally {
      setLoading(false)
    }
  }

  async function handleOpenFinderResult(folder: string) {
    if (!folder) return
    try { await openInFinder(folder) } catch { /* best-effort */ }
  }

  async function handleRescanResult(slug: string, folder: string) {
    if (!folder) return
    setRescanLoading(true)
    setError(null)
    try {
      const result = await scanFolder(folder, true)
      const recs = await getResults(result.slug)
      const res = await listResults()
      setResults(res)
      setSelectedSlug(result.slug)
      setRecords(recs)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Re-scan failed")
    } finally {
      setRescanLoading(false)
    }
  }

  async function handleDeleteResult(slug: string) {
    try {
      await deleteResult(slug)
      const res = await listResults()
      setResults(res)
      if (slug === selectedSlug) {
        setSelectedSlug(res[0]?.slug ?? null)
        if (res[0]) {
          const recs = await getResults(res[0].slug)
          setRecords(recs)
        } else {
          setRecords([])
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed")
    }
  }

  // ── Subfolder grouping for grid header injection ───────────────────────────
  type GridItem =
    | { type: "header"; subfolder: string; count: number }
    | { type: "record"; record: PhotoRecord }

  const gridItems = useMemo<GridItem[]>(() => {
    if (sortBy !== "subfolder") {
      return visible.map((r) => ({ type: "record" as const, record: r }))
    }
    const items: GridItem[] = []
    let lastSf: string | undefined = undefined
    for (const r of visible) {
      const sf = r._subfolder ?? ""
      if (sf !== lastSf) {
        lastSf = sf
        const count = subfolderMap.get(sf) ?? 0
        items.push({ type: "header", subfolder: sf, count })
      }
      items.push({ type: "record", record: r })
    }
    return items
  }, [visible, sortBy, subfolderMap])

  // ── Metric cards ───────────────────────────────────────────────────────────
  const topbarMetrics = [
    {
      label: "total",
      value: stats.total.toLocaleString(),
      color: "#e2e8f0",
    },
    {
      label: "safe to delete",
      value: `${stats.yes.toLocaleString()} · ${stats.yesGB.toFixed(2)} GB`,
      color: "#10b981",
    },
    {
      label: "keep",
      value: stats.no.toLocaleString(),
      color: "#f43f5e",
    },
    {
      label: "check",
      value: stats.maybe.toLocaleString(),
      color: "#f59e0b",
    },
  ]

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#060a10", color: "#e2e8f0", fontFamily: "-apple-system, 'SF Pro Text', system-ui, sans-serif" }}>
      {/* Sidebar */}
      <Sidebar
        results={results}
        selectedSlug={selectedSlug}
        onSelectSlug={(slug) => setSelectedSlug(slug)}
        filterStatus={filterStatus}
        onFilterStatus={setFilterStatus}
        search={search}
        onSearch={setSearch}
        sortBy={sortBy}
        onSortBy={setSortBy}
        sortDesc={sortDesc}
        onSortDesc={setSortDesc}
        subfolders={subfolderMap}
        selectedSubfolder={selectedSubfolder}
        onSelectSubfolder={setSelectedSubfolder}
        onScanClick={() => setScanOpen(true)}
        onRescanResult={handleRescanResult}
        onOpenFinderResult={handleOpenFinderResult}
        onDeleteResult={handleDeleteResult}
        stats={stats}
      />

      {/* Main area */}
      <div className="flex-1 flex flex-col overflow-hidden ml-[260px]">

        {/* Topbar */}
        <div
          className="px-6 py-4 flex items-center gap-4 shrink-0"
          style={{ borderBottom: "1px solid #1a2840" }}
        >
          {/* Metric cards */}
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {topbarMetrics.map((m) => (
              <div
                key={m.label}
                className="flex flex-col rounded-lg px-3 py-2"
                style={{ background: "#0d1625" }}
              >
                <span className="text-base font-semibold leading-tight" style={{ color: m.color }}>
                  {m.value}
                </span>
                <span className="text-xs leading-tight" style={{ color: "#4a6080" }}>
                  {m.label}
                </span>
              </div>
            ))}
          </div>

          {/* Right: loading / error */}
          <div className="shrink-0 flex items-center gap-2">
            {loading && (
              <div className="flex items-center gap-1.5" style={{ color: "#4a6080" }}>
                <Loader2 size={14} className="animate-spin" />
                <span className="text-xs">Loading…</span>
              </div>
            )}
            {error && (
              <span className="text-xs" style={{ color: "#f43f5e" }}>
                {error}
              </span>
            )}
          </div>
        </div>

        {/* Grid area */}
        <div className="flex-1 overflow-y-auto px-6 py-4 relative">

          {/* Loading state */}
          {loading && (
            <div className="flex flex-col items-center justify-center h-64 gap-3">
              <Loader2 size={36} className="animate-spin" style={{ color: "#3b82f6" }} />
              <span className="text-sm" style={{ color: "#4a6080" }}>Loading…</span>
            </div>
          )}

          {/* Rescan overlay — fixed so it covers the whole main area regardless of scroll */}
          {rescanLoading && (
            <div
              className="fixed inset-y-0 left-[260px] right-0 z-20 flex flex-col items-center justify-center gap-4"
              style={{ background: "rgba(6,10,16,0.85)", backdropFilter: "blur(4px)" }}
            >
              <div
                className="flex flex-col items-center gap-4 rounded-2xl px-10 py-8"
                style={{ background: "#0d1625", border: "1px solid #1a2840" }}
              >
                <Loader2 size={40} className="animate-spin" style={{ color: "#3b82f6" }} />
                <span className="text-sm font-medium" style={{ color: "#94a3b8" }}>
                  Re-scanning folder…
                </span>
                <span className="text-xs" style={{ color: "#4a6080" }}>
                  This may take a minute for large libraries
                </span>
              </div>
            </div>
          )}

          {/* No slug selected */}
          {!loading && !selectedSlug && (
            <div className="flex flex-col items-center justify-center h-64 gap-3">
              <span className="text-3xl" aria-hidden>📁</span>
              <p style={{ color: "#4a6080" }} className="text-sm">
                Select a result file or scan a folder
              </p>
            </div>
          )}

          {/* Slug selected but no results for current filter */}
          {!loading && selectedSlug && filtered.length === 0 && records.length > 0 && (
            <div className="flex flex-col items-center justify-center h-64 gap-3">
              <span className="text-3xl" aria-hidden>🔍</span>
              <p style={{ color: "#4a6080" }} className="text-sm">
                No photos match the current filter
              </p>
            </div>
          )}

          {/* Slug selected, records loaded, show grid */}
          {!loading && selectedSlug && filtered.length > 0 && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
                {gridItems.map((item, idx) => {
                  if (item.type === "header") {
                    return (
                      <div
                        key={`header-${item.subfolder}-${idx}`}
                        className="col-span-full flex items-center gap-2 pt-2 pb-1"
                      >
                        <span style={{ color: "#4a6080" }}>📁</span>
                        <span className="text-sm font-medium" style={{ color: "#94a3b8" }}>
                          {item.subfolder || "Root"}
                        </span>
                        <span
                          className="text-xs rounded px-1.5 py-0.5"
                          style={{ background: "#1a2840", color: "#4a6080" }}
                        >
                          {item.count}
                        </span>
                        <div className="flex-1 h-px" style={{ background: "#1a2840" }} />
                      </div>
                    )
                  }
                  const r = item.record
                  return (
                    <PhotoCard
                      key={r.path}
                      record={r}
                      index={filteredIndexMap.get(r.path) ?? -1}
                      selected={batch.has(r.path)}
                      onSelect={handleSelect}
                      onShiftSelect={handleShiftSelect}
                      onView={handleView}
                      thumbnailUrl={thumbnailUrl(r.path)}
                    />
                  )
                })}
              </div>

              {/* Infinite scroll sentinel */}
              <div ref={sentinelRef} className="h-4" />

              {/* Footer when all loaded */}
              {visibleCount >= filtered.length && (
                <p
                  className="text-center text-xs py-6"
                  style={{ color: "#4a6080" }}
                >
                  — {filtered.length} photos —
                </p>
              )}
            </>
          )}
        </div>
      </div>

      {/* Detail panel */}
      <DetailPanel
        record={detail}
        slug={selectedSlug ?? ""}
        onClose={handleClose}
        onImported={handleImported}
      />

      {/* Batch bar */}
      {batch.size > 0 && (
        <BatchBar
          batch={batch}
          records={records}
          slug={selectedSlug ?? ""}
          onClear={() => setBatch(new Set())}
          onDeleted={handleDeleted}
          onImported={handleImportedBatch}
          onSelectAll={handleSelectAll}
        />
      )}

      {/* Scan dialog */}
      <ScanDialog
        open={scanOpen}
        onClose={() => setScanOpen(false)}
        onScanned={handleScanned}
      />

      {/* Toast */}
      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}
    </div>
  )
}
