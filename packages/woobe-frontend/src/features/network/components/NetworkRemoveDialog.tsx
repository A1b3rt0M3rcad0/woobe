import { AlertTriangle, Trash2, X } from 'lucide-react'

export function NetworkRemoveDialog({
  title,
  description,
  impact,
  onClose,
  onConfirm,
}: {
  title: string
  description: string
  impact: string
  onClose: () => void
  onConfirm: () => void
}) {
  return <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"><div className="w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl"><header className="flex items-start gap-3 border-b border-border p-5"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-red-500/25 bg-red-500/5 text-red-300"><AlertTriangle className="h-4 w-4" /></div><div className="min-w-0 flex-1"><h2 className="text-sm font-semibold text-white">{title}</h2><p className="mt-1 text-[10px] leading-5 text-muted">{description}</p></div><button type="button" onClick={onClose} className="rounded-lg border border-border p-2 text-muted hover:text-white"><X className="h-4 w-4" /></button></header><div className="p-5"><div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-[10px] leading-5 text-amber-100">{impact}</div></div><footer className="flex justify-end gap-2 border-t border-border p-4"><button type="button" onClick={onClose} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Cancel</button><button type="button" onClick={onConfirm} className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[10px] font-medium text-red-200"><Trash2 className="h-3.5 w-3.5" />Remove</button></footer></div></div>
}

