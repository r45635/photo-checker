"use client"

import { useState } from "react"
import { X, Upload, Trash2, AlertTriangle, CheckSquare } from "lucide-react"
import type { PhotoRecord } from "@/lib/types"
import { deletePhotos, movePhotos, importPhoto, pickFolder } from "@/lib/api"

interface BatchBarProps {
  batch: Set<string>
  records: PhotoRecord[]
  slug: string
  onClear: () => void
  onDeleted: (paths: string[], message: string) => void
  onImported: (paths: string[]) => void
  onSelectAll: () => void
}

type ConfirmState =
  | null
  | { type: "trash"; step: 1; progress: number | null }
  | { type: "force"; step: 1; destFolder: string }
  | { type: "force"; step: 2; destFolder: string; typedText: string; progress: number | null }
  | { type: "import"; step: 1; progress: number | null }

export default function BatchBar({
  batch,
  records,
  slug,
  onClear,
  onDeleted,
  onImported,
  onSelectAll,
}: BatchBarProps) {
  const [confirmState, setConfirmState] = useState<ConfirmState>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const batchRecords = records.filter((r) => batch.has(r.path))

  const totalSizeKb = batchRecords.reduce((sum, r) => sum + r.size_kb, 0)
  const totalSizeMb = (totalSizeKb / 1024).toFixed(1)

  const yesCount = batchRecords.filter((r) => r.safe_to_delete === "YES").length
  const noCount = batchRecords.filter((r) => r.safe_to_delete === "NO").length
  const maybeCount = batchRecords.filter((r) => r.safe_to_delete === "MAYBE").length

  const canImport = batchRecords.filter((r) => r.safe_to_delete === "NO")
  const canDelete = batchRecords.filter((r) => r.safe_to_delete === "YES")
  const canForce = batchRecords.filter(
    (r) => r.safe_to_delete === "NO" || r.safe_to_delete === "MAYBE"
  )

  const visible = batch.size > 0

  function handleTrashClick() {
    setErrorMsg(null)
    setConfirmState({ type: "trash", step: 1, progress: null })
  }

  function handleForceClick() {
    setErrorMsg(null)
    setConfirmState({ type: "force", step: 1, destFolder: "" })
  }

  function handleImportClick() {
    setErrorMsg(null)
    setConfirmState({ type: "import", step: 1, progress: null })
  }

  function closeConfirm() {
    setConfirmState(null)
    setErrorMsg(null)
  }

  async function executeTrash() {
    setIsProcessing(true)
    setErrorMsg(null)
    const paths = canDelete.map((r) => r.path)
    try {
      for (let i = 0; i < paths.length; i++) {
        setConfirmState({ type: "trash", step: 1, progress: i })
        await deletePhotos([paths[i]], slug)
      }
      closeConfirm()
      onDeleted(paths, `${paths.length} file${paths.length !== 1 ? "s" : ""} moved to Trash`)
    } catch (e: any) {
      setErrorMsg(e.message ?? "Delete failed")
    } finally {
      setIsProcessing(false)
    }
  }

  async function executeForce(destFolder: string) {
    setIsProcessing(true)
    setErrorMsg(null)
    const paths = canForce.map((r) => r.path)
    const isMove = !!destFolder.trim()
    try {
      for (let i = 0; i < paths.length; i++) {
        setConfirmState({ type: "force", step: 2, destFolder, typedText: "DELETE", progress: i })
        if (isMove) {
          await movePhotos([paths[i]], destFolder.trim(), slug)
        } else {
          await deletePhotos([paths[i]], slug)
        }
      }
      closeConfirm()
      const verb = isMove ? "moved" : "moved to Trash"
      onDeleted(paths, `${paths.length} file${paths.length !== 1 ? "s" : ""} ${verb}`)
    } catch (e: any) {
      setErrorMsg(e.message ?? "Operation failed")
    } finally {
      setIsProcessing(false)
    }
  }

  async function executeImport() {
    setIsProcessing(true)
    setErrorMsg(null)
    const succeeded: string[] = []
    const failed: string[] = []
    for (let i = 0; i < canImport.length; i++) {
      setConfirmState({ type: "import", step: 1, progress: i })
      try {
        await importPhoto(canImport[i].path)
        succeeded.push(canImport[i].path)
      } catch {
        failed.push(canImport[i].filename)
      }
    }
    setIsProcessing(false)
    if (failed.length > 0) {
      setErrorMsg(`${failed.length} import(s) failed: ${failed.slice(0, 3).join(", ")}${failed.length > 3 ? ` … +${failed.length - 3}` : ""}`)
    } else {
      closeConfirm()
    }
    if (succeeded.length > 0) onImported(succeeded)
  }

  return (
    <>
      {/* Confirmation overlay */}
      {confirmState && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/50"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeConfirm()
          }}
        >
          <div className="relative w-full max-w-md rounded-2xl border border-[#1a2840] bg-[#0d1625] p-6 shadow-2xl">
            {/* TRASH confirmation */}
            {confirmState.type === "trash" && (
              <>
                <h2 className="mb-1 text-base font-semibold text-slate-200">Move to Trash?</h2>
                <p className="mb-4 text-xs text-[#4a6080]">
                  Recoverable from macOS Trash.
                </p>
                {canDelete.some(r => r.match_confidence === "medium") && (
                  <div className="mb-3 flex items-start gap-2 rounded-lg bg-amber-900/30 px-3 py-2 text-xs text-amber-400">
                    <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                    <span>
                      Some files were matched indirectly (copy suffix or format conversion).
                      Review before deleting.
                    </span>
                  </div>
                )}
                <FilenameList records={canDelete} />
                {confirmState.progress !== null && (
                  <div className="mt-4">
                    <div className="mb-1 flex justify-between text-xs text-[#4a6080]">
                      <span>Moving…</span>
                      <span>{confirmState.progress + 1} / {canDelete.length}</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#1a2840]">
                      <div
                        className="h-full rounded-full bg-rose-500 transition-all duration-200"
                        style={{ width: `${Math.round(((confirmState.progress + 1) / canDelete.length) * 100)}%` }}
                      />
                    </div>
                  </div>
                )}
                {errorMsg && (
                  <p className="mt-3 text-xs text-rose-400">{errorMsg}</p>
                )}
                <div className="mt-5 flex justify-end gap-2">
                  <button
                    onClick={closeConfirm}
                    disabled={isProcessing}
                    className="rounded-lg border border-[#1a2840] px-4 py-2 text-sm font-medium text-slate-400 transition-colors duration-150 hover:border-[#2a3850] hover:text-slate-300 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={executeTrash}
                    disabled={isProcessing}
                    className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white transition-opacity duration-150 hover:opacity-90 disabled:opacity-50"
                  >
                    {isProcessing ? "Moving…" : `Trash ${canDelete.length}`}
                  </button>
                </div>
              </>
            )}

            {/* FORCE DELETE — step 1 */}
            {confirmState.type === "force" && confirmState.step === 1 && (
              <>
                <div className="mb-3 flex items-center gap-2 text-amber-400">
                  <AlertTriangle size={16} />
                  <h2 className="text-base font-semibold">Warning: No confirmed backup!</h2>
                </div>
                <p className="mb-4 text-xs text-[#4a6080]">
                  These files have NO confirmed backup. You can optionally move them to a
                  destination folder instead of trashing them.
                </p>
                <FilenameList records={canForce} />
                <div className="mt-4">
                  <label className="mb-1 block text-xs text-[#4a6080]">
                    Destination folder (optional — leave blank to trash)
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={confirmState.destFolder}
                      onChange={(e) =>
                        setConfirmState({ ...confirmState, destFolder: e.target.value })
                      }
                      placeholder="/path/to/folder"
                      className="flex-1 rounded-lg border border-[#1a2840] bg-[#060a10] px-3 py-2 text-sm text-slate-300 placeholder-[#4a6080] outline-none focus:border-[#3b82f6] transition-colors duration-150"
                    />
                    <button
                      onClick={async () => {
                        const p = await pickFolder()
                        if (p) setConfirmState({ ...confirmState, destFolder: p })
                      }}
                      className="rounded-lg border border-[#1a2840] px-3 py-2 text-xs text-slate-400 transition-colors duration-150 hover:border-[#2a3850] hover:text-slate-300"
                    >
                      Browse
                    </button>
                  </div>
                </div>
                {errorMsg && (
                  <p className="mt-3 text-xs text-rose-400">{errorMsg}</p>
                )}
                <div className="mt-5 flex justify-end gap-2">
                  <button
                    onClick={closeConfirm}
                    className="rounded-lg border border-[#1a2840] px-4 py-2 text-sm font-medium text-slate-400 transition-colors duration-150 hover:border-[#2a3850] hover:text-slate-300"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() =>
                      setConfirmState({
                        type: "force",
                        step: 2,
                        destFolder: confirmState.destFolder,
                        typedText: "",
                        progress: null,
                      })
                    }
                    className="rounded-lg border border-rose-500/50 px-4 py-2 text-sm font-medium text-rose-400 transition-colors duration-150 hover:border-rose-500 hover:text-rose-300"
                  >
                    Continue
                  </button>
                </div>
              </>
            )}

            {/* FORCE DELETE — step 2 */}
            {confirmState.type === "force" && confirmState.step === 2 && (
              <>
                <div className="mb-3 flex items-center gap-2 text-rose-400">
                  <AlertTriangle size={16} />
                  <h2 className="text-base font-semibold">Final confirmation</h2>
                </div>
                <p className="mb-4 text-xs text-[#4a6080]">
                  Type{" "}
                  <span className="font-mono font-bold text-rose-400">DELETE</span> to
                  confirm deletion of {canForce.length} file(s).
                </p>
                <input
                  type="text"
                  value={confirmState.typedText}
                  onChange={(e) =>
                    setConfirmState({ ...confirmState, typedText: e.target.value })
                  }
                  placeholder="DELETE"
                  className="w-full rounded-lg border border-[#1a2840] bg-[#060a10] px-3 py-2 text-sm text-slate-300 placeholder-[#4a6080] outline-none focus:border-rose-500/50 transition-colors duration-150"
                  autoFocus
                />
                {confirmState.progress !== null && (
                  <div className="mt-4">
                    <div className="mb-1 flex justify-between text-xs text-[#4a6080]">
                      <span>Processing…</span>
                      <span>{confirmState.progress + 1} / {canForce.length}</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#1a2840]">
                      <div
                        className="h-full rounded-full bg-rose-500 transition-all duration-200"
                        style={{ width: `${Math.round(((confirmState.progress + 1) / canForce.length) * 100)}%` }}
                      />
                    </div>
                  </div>
                )}
                {errorMsg && (
                  <p className="mt-3 text-xs text-rose-400">{errorMsg}</p>
                )}
                <div className="mt-5 flex justify-end gap-2">
                  <button
                    onClick={closeConfirm}
                    disabled={isProcessing}
                    className="rounded-lg border border-[#1a2840] px-4 py-2 text-sm font-medium text-slate-400 transition-colors duration-150 hover:border-[#2a3850] hover:text-slate-300 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => executeForce(confirmState.destFolder)}
                    disabled={confirmState.typedText !== "DELETE" || isProcessing}
                    className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white transition-opacity duration-150 hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
                  >
                    {isProcessing ? "Processing…" : "Execute"}
                  </button>
                </div>
              </>
            )}

            {/* IMPORT confirmation */}
            {confirmState.type === "import" && (
              <>
                <div className="mb-1 flex items-center gap-2 text-emerald-400">
                  <Upload size={16} />
                  <h2 className="text-base font-semibold">Import to Apple Photos?</h2>
                </div>
                <p className="mb-4 text-xs text-[#4a6080]">
                  {canImport.length} file(s) will be imported into your Apple Photos library.
                </p>
                <FilenameList records={canImport} />
                {confirmState.progress !== null && (
                  <div className="mt-4">
                    <div className="mb-1 flex justify-between text-xs text-[#4a6080]">
                      <span>Importing…</span>
                      <span>
                        {confirmState.progress + 1} / {canImport.length}
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#1a2840]">
                      <div
                        className="h-full rounded-full bg-emerald-500 transition-all duration-200"
                        style={{
                          width: `${Math.round(
                            ((confirmState.progress + 1) / canImport.length) * 100
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
                {errorMsg && (
                  <p className="mt-3 text-xs text-rose-400">{errorMsg}</p>
                )}
                <div className="mt-5 flex justify-end gap-2">
                  <button
                    onClick={closeConfirm}
                    disabled={isProcessing}
                    className="rounded-lg border border-[#1a2840] px-4 py-2 text-sm font-medium text-slate-400 transition-colors duration-150 hover:border-[#2a3850] hover:text-slate-300 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={executeImport}
                    disabled={isProcessing}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-opacity duration-150 hover:opacity-90 disabled:opacity-50"
                  >
                    {isProcessing ? "Importing…" : `Import ${canImport.length}`}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Bottom bar */}
      <div
        className={`fixed bottom-0 left-[260px] right-0 z-30 flex h-16 items-center gap-4 border-t border-[#1a2840] bg-[#0a1220]/95 px-6 backdrop-blur-xl transition-transform duration-200 ease-out ${
          visible ? "translate-y-0" : "translate-y-full"
        }`}
      >
        {/* Left: summary */}
        <div className="flex-1 min-w-0">
          <p className="truncate text-sm font-medium text-slate-300">
            {batch.size} photo{batch.size !== 1 ? "s" : ""} selected · {totalSizeMb} MB
          </p>
          <p className="text-xs text-[#4a6080]">
            {yesCount > 0 && (
              <span className="text-emerald-500">{yesCount} YES</span>
            )}
            {yesCount > 0 && (noCount > 0 || maybeCount > 0) && (
              <span> · </span>
            )}
            {noCount > 0 && (
              <span className="text-rose-400">{noCount} NO</span>
            )}
            {noCount > 0 && maybeCount > 0 && (
              <span> · </span>
            )}
            {maybeCount > 0 && (
              <span className="text-amber-400">{maybeCount} MAYBE</span>
            )}
          </p>
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-2">
          {/* Select all visible */}
          <button
            onClick={onSelectAll}
            className="flex items-center gap-1.5 rounded-lg border border-[#1a2840] px-3 py-2 text-xs font-medium text-slate-400 transition-colors duration-150 hover:border-[#2a3850] hover:text-slate-300"
          >
            <CheckSquare size={12} />
            Select all visible
          </button>

          {/* Import */}
          {canImport.length > 0 && (
            <button
              onClick={handleImportClick}
              className="flex items-center gap-1.5 rounded-lg border border-emerald-600/30 bg-emerald-600/20 px-4 py-2 text-sm font-medium text-emerald-400 transition-colors duration-150 hover:bg-emerald-600/30"
            >
              <Upload size={14} />
              Import {canImport.length}
            </button>
          )}

          {/* Trash */}
          {canDelete.length > 0 && (
            <button
              onClick={handleTrashClick}
              className="flex items-center gap-1.5 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white transition-opacity duration-150 hover:opacity-90"
            >
              <Trash2 size={14} />
              Trash {canDelete.length}
            </button>
          )}

          {/* Force delete */}
          {canForce.length > 0 && (
            <button
              onClick={handleForceClick}
              className="flex items-center gap-1.5 rounded-lg border border-rose-500/50 px-4 py-2 text-xs font-medium text-rose-400 transition-colors duration-150 hover:border-rose-500 hover:text-rose-300"
            >
              <AlertTriangle size={12} />
              Force delete {canForce.length}
            </button>
          )}

          {/* Clear selection */}
          <button
            onClick={onClear}
            className="ml-1 rounded-lg p-1.5 text-slate-500 transition-colors duration-150 hover:text-slate-300"
            aria-label="Clear selection"
          >
            <X size={16} />
          </button>
        </div>
      </div>
    </>
  )
}

function FilenameList({ records }: { records: PhotoRecord[] }) {
  const MAX = 8
  const shown = records.slice(0, MAX)
  const overflow = records.length - MAX

  return (
    <ul className="max-h-36 overflow-y-auto rounded-lg border border-[#1a2840] bg-[#060a10] px-3 py-2">
      {shown.map((r) => (
        <li key={r.filename} className="truncate py-0.5 font-mono text-xs text-slate-400">
          {r.filename}
        </li>
      ))}
      {overflow > 0 && (
        <li className="py-0.5 text-xs text-[#4a6080]">…and {overflow} more</li>
      )}
    </ul>
  )
}
