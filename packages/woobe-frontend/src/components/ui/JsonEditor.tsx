import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { Copy, Check, Paintbrush, AlertCircle, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatJsonSafely, validateJson, type ValidationResult } from '@/lib/json-utils'
import { jsonDarkTheme, jsonSyntaxHighlight } from './json-cm-theme'

interface JsonEditorProps {
  value?: string | null
  onChange?: (value: string) => void
  onValidJsonChange?: (json: unknown) => void
  editable?: boolean
  title?: string
  actions?: ('format' | 'validate' | 'copy' | 'clear')[]
  minHeight?: number
  maxHeight?: number | string
  placeholder?: string
  disabled?: boolean
  className?: string
  error?: string | null
  hideError?: boolean
}

export function JsonEditor({
  value = '',
  onChange,
  onValidJsonChange,
  editable = true,
  title,
  actions = ['format', 'validate'],
  minHeight = 180,
  maxHeight,
  placeholder,
  disabled = false,
  className,
  error: externalError,
  hideError = false,
}: JsonEditorProps) {
  const [internalValue, setInternalValue] = useState(value ?? '')
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [copied, setCopied] = useState(false)
  const prevValueRef = useRef(value)

  useEffect(() => {
    if (value !== prevValueRef.current) {
      setInternalValue(value ?? '')
      prevValueRef.current = value
    }
  }, [value])

  const handleChange = useCallback(
    (val: string) => {
      setInternalValue(val)
      onChange?.(val)
      if (val.trim()) {
        const result = formatJsonSafely(val)
        if (result.ok && onValidJsonChange) {
          onValidJsonChange(JSON.parse(val))
        }
      }
      if (validation) setValidation(null)
    },
    [onChange, onValidJsonChange, validation],
  )

  const handleFormat = useCallback(() => {
    const result = formatJsonSafely(internalValue)
    if (result.ok) {
      setInternalValue(result.value)
      onChange?.(result.value)
    } else {
      setValidation({ valid: false, error: result.error, line: result.line, col: result.col })
    }
  }, [internalValue, onChange])

  const handleValidate = useCallback(() => {
    const result = validateJson(internalValue)
    setValidation(result)
    if (result.valid && onValidJsonChange) {
      try {
        onValidJsonChange(JSON.parse(internalValue))
      } catch {}
    }
  }, [internalValue, onValidJsonChange])

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(internalValue)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [internalValue])

  const handleClear = useCallback(() => {
    setInternalValue('')
    onChange?.('')
    setValidation(null)
  }, [onChange])

  const errorMessage = useMemo(() => {
    if (externalError) return externalError
    if (validation && !validation.valid) {
      const { error, line, col } = validation
      let msg = error
      if (line != null && col != null) {
        msg += ` (line ${line}, col ${col})`
      } else if (line != null) {
        msg += ` (line ${line})`
      }
      return msg
    }
    return null
  }, [externalError, validation])

  const validationSuccess = validation?.valid === true

  const hasTopBar = title || (editable && actions.length > 0)
  const maxH = maxHeight ? (typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight) : undefined

  return (
    <div className={cn('space-y-2', className)}>
      {hasTopBar && (
        <div className="flex items-center justify-between gap-2">
          {title && <span className="text-xs font-medium text-muted truncate">{title}</span>}
          {editable && actions.length > 0 && (
            <div className="flex items-center gap-1 shrink-0">
              {actions.includes('format') && (
                <button
                  type="button"
                  onClick={handleFormat}
                  className="inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium text-muted hover:text-white hover:bg-accent transition-colors"
                  title="Format JSON"
                >
                  <Paintbrush className="h-3 w-3" />
                  Format
                </button>
              )}
              {actions.includes('validate') && (
                <button
                  type="button"
                  onClick={handleValidate}
                  className="inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium text-muted hover:text-white hover:bg-accent transition-colors"
                  title={`Validate JSON${validationSuccess ? ' — Valid!' : ''}`}
                >
                  <AlertCircle className="h-3 w-3" />
                  Validate
                  {validationSuccess && <Check className="h-3 w-3 text-emerald-400" />}
                </button>
              )}
              {actions.includes('copy') && internalValue && (
                <button
                  type="button"
                  onClick={handleCopy}
                  className="p-1 rounded text-muted hover:text-white hover:bg-accent transition-colors"
                  title={copied ? 'Copied!' : 'Copy'}
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              )}
              {actions.includes('clear') && internalValue && (
                <button
                  type="button"
                  onClick={handleClear}
                  className="p-1 rounded text-muted hover:text-white hover:bg-accent transition-colors"
                  title="Clear"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          )}
        </div>
      )}
      <div
        className={cn(
          'rounded-lg border scrollbar-thin overflow-auto transition-colors',
          errorMessage ? 'border-rose-500/50' : validationSuccess ? 'border-emerald-500/50' : 'border-[#24324A]',
        )}
        style={{ minHeight: `${minHeight}px`, maxHeight: maxH }}
      >
        <CodeMirror
          value={internalValue}
          onChange={handleChange}
          extensions={[json(), jsonDarkTheme, jsonSyntaxHighlight]}
          readOnly={!editable || disabled}
          basicSetup={{
            lineNumbers: true,
            foldGutter: true,
            highlightActiveLine: true,
            highlightActiveLineGutter: true,
          }}
          placeholder={placeholder}
          className={cn(
            disabled && 'opacity-50 pointer-events-none',
          )}
          theme="none"
        />
      </div>
      {!hideError && errorMessage && (
        <div className="flex items-start gap-1.5 rounded-md bg-rose-500/10 border border-rose-500/20 px-2.5 py-1.5">
          <AlertCircle className="h-3.5 w-3.5 text-rose-400 shrink-0 mt-0.5" />
          <p className="text-[11px] text-rose-300 leading-relaxed">{errorMessage}</p>
        </div>
      )}
      {!hideError && validationSuccess && (
        <div className="flex items-center gap-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1.5">
          <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
          <p className="text-[11px] text-emerald-300">Valid JSON</p>
        </div>
      )}
    </div>
  )
}
