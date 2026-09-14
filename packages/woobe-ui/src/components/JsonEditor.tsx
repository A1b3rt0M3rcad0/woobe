import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { AlertCircle, Check, Copy, Paintbrush, X } from 'lucide-react'
import { Button } from './Button'
import { cn } from '../lib/cn'
import { formatJsonSafely, validateJson, type ValidationResult } from '../lib/json'
import { jsonDarkTheme, jsonSyntaxHighlight } from '../lib/json-codemirror'
import { woobeLayout } from '../tokens'

export interface JsonEditorProps {
  value?: string | null
  onChange?: (value: string) => void
  onValidJsonChange?: (json: unknown) => void
  editable?: boolean
  title?: string
  actions?: ('format' | 'validate' | 'copy' | 'clear')[]
  minHeight?: number | string
  maxHeight?: number | string
  placeholder?: string
  disabled?: boolean
  className?: string
  error?: string | null
  hideError?: boolean
}

function cssSize(value?: number | string) {
  if (value === undefined) return undefined
  return typeof value === 'number' ? `${value}px` : value
}

export function JsonEditor({
  value = '',
  onChange,
  onValidJsonChange,
  editable = true,
  title,
  actions = ['format', 'validate'],
  minHeight = woobeLayout.codeEditorCompact,
  maxHeight = woobeLayout.codeEditorMax,
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

  const handleChange = useCallback((nextValue: string) => {
    setInternalValue(nextValue)
    onChange?.(nextValue)
    if (nextValue.trim()) {
      const result = formatJsonSafely(nextValue)
      if (result.ok && onValidJsonChange) onValidJsonChange(JSON.parse(nextValue))
    }
    if (validation) setValidation(null)
  }, [onChange, onValidJsonChange, validation])

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
      try { onValidJsonChange(JSON.parse(internalValue)) } catch {}
    }
  }, [internalValue, onValidJsonChange])

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(internalValue)
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
      let message = error
      if (line != null && col != null) message += ` (line ${line}, col ${col})`
      else if (line != null) message += ` (line ${line})`
      return message
    }
    return null
  }, [externalError, validation])

  const validationSuccess = validation?.valid === true
  const hasTopBar = title || (editable && actions.length > 0)

  return (
    <div className={cn('space-y-ui-sm', className)}>
      {hasTopBar ? (
        <div className="flex items-center justify-between gap-ui-sm">
          {title ? <span className="truncate font-mono text-system-label font-medium text-muted-foreground">{title}</span> : null}
          {editable && actions.length > 0 ? (
            <div className="flex shrink-0 items-center gap-ui-xs">
              {actions.includes('format') ? <Button type="button" variant="ghost" size="xs" onClick={handleFormat} className="gap-ui-xs text-muted-foreground" title="Format JSON"><Paintbrush className="h-icon-sm w-icon-sm" />Format</Button> : null}
              {actions.includes('validate') ? <Button type="button" variant="ghost" size="xs" onClick={handleValidate} className="gap-ui-xs text-muted-foreground" title={`Validate JSON${validationSuccess ? ' — Valid!' : ''}`}><AlertCircle className="h-icon-sm w-icon-sm" />Validate{validationSuccess ? <Check className="h-icon-sm w-icon-sm text-success" /> : null}</Button> : null}
              {actions.includes('copy') && internalValue ? <Button type="button" variant="ghost" size="iconXs" onClick={handleCopy} className="text-muted-foreground" title={copied ? 'Copied!' : 'Copy'} aria-label="Copy JSON">{copied ? <Check className="h-icon-sm w-icon-sm text-success" /> : <Copy className="h-icon-sm w-icon-sm" />}</Button> : null}
              {actions.includes('clear') && internalValue ? <Button type="button" variant="ghost" size="iconXs" onClick={handleClear} className="text-muted-foreground" title="Clear" aria-label="Clear JSON"><X className="h-icon-sm w-icon-sm" /></Button> : null}
            </div>
          ) : null}
        </div>
      ) : null}
      <div
        className={cn(
          'overflow-auto rounded-container border bg-background/30 scrollbar-thin transition-colors',
          errorMessage ? 'border-error/50' : validationSuccess ? 'border-success/50' : 'border-border',
        )}
        style={{ minHeight: cssSize(minHeight), maxHeight: cssSize(maxHeight) }}
      >
        <CodeMirror
          value={internalValue}
          onChange={handleChange}
          extensions={[json(), jsonDarkTheme, jsonSyntaxHighlight]}
          readOnly={!editable || disabled}
          basicSetup={{ lineNumbers: true, foldGutter: true, highlightActiveLine: true, highlightActiveLineGutter: true }}
          placeholder={placeholder}
          className={cn(disabled && 'pointer-events-none opacity-50')}
          theme="none"
        />
      </div>
      {!hideError && errorMessage ? <div className="flex items-start gap-ui-xs rounded-container border border-error/20 bg-error/10 px-ui-sm py-ui-sm"><AlertCircle className="mt-ui-hairline h-icon w-icon shrink-0 text-error" /><p className="font-sans text-product-small text-error">{errorMessage}</p></div> : null}
      {!hideError && validationSuccess ? <div className="flex items-center gap-ui-xs rounded-container border border-success/20 bg-success/10 px-ui-sm py-ui-sm"><Check className="h-icon w-icon shrink-0 text-success" /><p className="font-sans text-product-small text-success">Valid JSON</p></div> : null}
    </div>
  )
}
