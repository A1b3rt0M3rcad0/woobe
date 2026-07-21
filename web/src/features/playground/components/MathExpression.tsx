import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface MathExpressionProps {
  expression: string
  display?: boolean
  className?: string
}

const SYMBOL_COMMANDS: Record<string, string> = {
  alpha: 'α',
  beta: 'β',
  gamma: 'γ',
  delta: 'δ',
  epsilon: 'ε',
  varepsilon: 'ϵ',
  zeta: 'ζ',
  eta: 'η',
  theta: 'θ',
  vartheta: 'ϑ',
  iota: 'ι',
  kappa: 'κ',
  lambda: 'λ',
  mu: 'μ',
  nu: 'ν',
  xi: 'ξ',
  omicron: 'ο',
  pi: 'π',
  varpi: 'ϖ',
  rho: 'ρ',
  varrho: 'ϱ',
  sigma: 'σ',
  varsigma: 'ς',
  tau: 'τ',
  upsilon: 'υ',
  phi: 'φ',
  varphi: 'ϕ',
  chi: 'χ',
  psi: 'ψ',
  omega: 'ω',
  Gamma: 'Γ',
  Delta: 'Δ',
  Theta: 'Θ',
  Lambda: 'Λ',
  Xi: 'Ξ',
  Pi: 'Π',
  Sigma: 'Σ',
  Upsilon: 'Υ',
  Phi: 'Φ',
  Psi: 'Ψ',
  Omega: 'Ω',
  infty: '∞',
  partial: '∂',
  nabla: '∇',
  ell: 'ℓ',
  hbar: 'ℏ',
  imath: 'ı',
  jmath: 'ȷ',
  sum: '∑',
  prod: '∏',
  coprod: '∐',
  int: '∫',
  iint: '∬',
  iiint: '∭',
  oint: '∮',
  bigcup: '⋃',
  bigcap: '⋂',
  bigvee: '⋁',
  bigwedge: '⋀',
  le: '≤',
  leq: '≤',
  ge: '≥',
  geq: '≥',
  neq: '≠',
  ne: '≠',
  approx: '≈',
  sim: '∼',
  simeq: '≃',
  equiv: '≡',
  propto: '∝',
  cong: '≅',
  to: '→',
  rightarrow: '→',
  leftarrow: '←',
  leftrightarrow: '↔',
  Rightarrow: '⇒',
  Leftarrow: '⇐',
  Leftrightarrow: '⇔',
  mapsto: '↦',
  hookrightarrow: '↪',
  hookleftarrow: '↩',
  uparrow: '↑',
  downarrow: '↓',
  updownarrow: '↕',
  times: '×',
  cdot: '⋅',
  ast: '∗',
  star: '⋆',
  div: '÷',
  pm: '±',
  mp: '∓',
  circ: '∘',
  bullet: '•',
  cap: '∩',
  cup: '∪',
  subset: '⊂',
  subseteq: '⊆',
  supset: '⊃',
  supseteq: '⊇',
  in: '∈',
  notin: '∉',
  ni: '∋',
  forall: '∀',
  exists: '∃',
  nexists: '∄',
  neg: '¬',
  land: '∧',
  wedge: '∧',
  lor: '∨',
  vee: '∨',
  angle: '∠',
  measuredangle: '∡',
  degree: '°',
  prime: '′',
  emptyset: '∅',
  varnothing: '∅',
  top: '⊤',
  bot: '⊥',
  parallel: '∥',
  perp: '⊥',
  ldots: '…',
  dots: '…',
  cdots: '⋯',
  vdots: '⋮',
  ddots: '⋱',
}

const DELIMITER_COMMANDS: Record<string, string> = {
  lbrace: '{',
  rbrace: '}',
  langle: '⟨',
  rangle: '⟩',
  lceil: '⌈',
  rceil: '⌉',
  lfloor: '⌊',
  rfloor: '⌋',
  vert: '|',
  Vert: '‖',
  backslash: '\\',
}

const FUNCTION_COMMANDS = new Set([
  'sin',
  'cos',
  'tan',
  'cot',
  'sec',
  'csc',
  'arcsin',
  'arccos',
  'arctan',
  'sinh',
  'cosh',
  'tanh',
  'log',
  'ln',
  'exp',
  'lim',
  'limsup',
  'liminf',
  'max',
  'min',
  'sup',
  'inf',
  'det',
  'gcd',
  'mod',
])

const SPACING_COMMANDS: Record<string, string> = {
  ',': '0.17em',
  ':': '0.22em',
  ';': '0.28em',
  '!': '-0.12em',
  quad: '1em',
  qquad: '2em',
  enspace: '0.5em',
  thinspace: '0.17em',
}

const ACCENT_COMMANDS: Record<string, string> = {
  hat: '^',
  widehat: '^',
  bar: '¯',
  overline: '¯',
  vec: '→',
  dot: '˙',
  ddot: '¨',
  tilde: '~',
  widetilde: '~',
  breve: '˘',
  check: 'ˇ',
}

function textFromRawGroup(value: string): string {
  return value
    .replace(/\\([{}_$%&#])/g, '$1')
    .replace(/~/g, ' ')
}

function splitTopLevel(source: string, separator: '&' | '\\\\'): string[] {
  const parts: string[] = []
  let current = ''
  let braceDepth = 0

  for (let index = 0; index < source.length; index++) {
    const char = source[index]
    const next = source[index + 1]

    if (char === '{') braceDepth += 1
    if (char === '}') braceDepth = Math.max(0, braceDepth - 1)

    if (braceDepth === 0 && separator === '&' && char === '&') {
      parts.push(current)
      current = ''
      continue
    }

    if (braceDepth === 0 && separator === '\\\\' && char === '\\' && next === '\\') {
      parts.push(current)
      current = ''
      index += 1
      continue
    }

    current += char
  }

  parts.push(current)
  return parts
}

class LatexMathParser {
  private index = 0
  private key = 0

  constructor(private readonly source: string) {}

  parseRoot(): ReactNode[] {
    return this.parseSequence()
  }

  private nextKey(prefix: string): string {
    this.key += 1
    return `${prefix}-${this.key}`
  }

  private peek(offset = 0): string {
    return this.source[this.index + offset] ?? ''
  }

  private skipWhitespace(): void {
    while (/\s/.test(this.peek())) this.index += 1
  }

  private parseSequence(stopCharacter?: string): ReactNode[] {
    const nodes: ReactNode[] = []

    while (this.index < this.source.length) {
      if (stopCharacter && this.peek() === stopCharacter) {
        this.index += 1
        break
      }

      if (/\s/.test(this.peek())) {
        this.skipWhitespace()
        continue
      }

      nodes.push(this.parseAtomWithScripts())
    }

    return nodes
  }

  private parseAtomWithScripts(): ReactNode {
    const base = this.parseBase()
    let subscript: ReactNode | null = null
    let superscript: ReactNode | null = null

    while (this.index < this.source.length) {
      this.skipWhitespace()
      const marker = this.peek()
      if (marker !== '_' && marker !== '^') break
      this.index += 1
      const script = this.parseScriptArgument()
      if (marker === '_') subscript = script
      else superscript = script
    }

    if (subscript && superscript) {
      return (
        <msubsup key={this.nextKey('subsup')}>
          {base}
          {subscript}
          {superscript}
        </msubsup>
      )
    }

    if (subscript) {
      return (
        <msub key={this.nextKey('sub')}>
          {base}
          {subscript}
        </msub>
      )
    }

    if (superscript) {
      return (
        <msup key={this.nextKey('sup')}>
          {base}
          {superscript}
        </msup>
      )
    }

    return base
  }

  private parseScriptArgument(): ReactNode {
    this.skipWhitespace()
    if (this.peek() === '{') {
      this.index += 1
      return <mrow key={this.nextKey('script-group')}>{this.parseSequence('}')}</mrow>
    }
    return this.parseBase()
  }

  private parseBase(): ReactNode {
    const char = this.peek()

    if (!char) return <mrow key={this.nextKey('empty')} />

    if (char === '{') {
      this.index += 1
      return <mrow key={this.nextKey('group')}>{this.parseSequence('}')}</mrow>
    }

    if (char === '\\') return this.parseCommand()

    if (/[0-9]/.test(char)) {
      let value = ''
      while (/[0-9.,]/.test(this.peek())) {
        value += this.peek()
        this.index += 1
      }
      return <mn key={this.nextKey('number')}>{value}</mn>
    }

    if (/[A-Za-zÀ-ÖØ-öø-ÿΑ-ω]/.test(char)) {
      this.index += 1
      return <mi key={this.nextKey('identifier')}>{char}</mi>
    }

    this.index += 1
    const operator = char === '*' ? '⋅' : char
    return <mo key={this.nextKey('operator')}>{operator}</mo>
  }

  private readCommandName(): string {
    if (this.peek() !== '\\') return ''
    this.index += 1

    let command = ''
    while (/[A-Za-z]/.test(this.peek())) {
      command += this.peek()
      this.index += 1
    }

    if (!command && this.peek()) {
      command = this.peek()
      this.index += 1
    }

    return command
  }

  private parseCommand(): ReactNode {
    const command = this.readCommandName()

    if (command === 'frac' || command === 'dfrac' || command === 'tfrac') {
      const numerator = this.parseRequiredGroup()
      const denominator = this.parseRequiredGroup()
      return (
        <mfrac key={this.nextKey('fraction')}>
          {numerator}
          {denominator}
        </mfrac>
      )
    }

    if (command === 'sqrt') {
      const optionalIndex = this.readOptionalRawGroup()
      const radicand = this.parseRequiredGroup()
      if (optionalIndex != null) {
        const indexNodes = new LatexMathParser(optionalIndex).parseRoot()
        return (
          <mroot key={this.nextKey('root')}>
            {radicand}
            <mrow>{indexNodes}</mrow>
          </mroot>
        )
      }
      return <msqrt key={this.nextKey('sqrt')}>{radicand}</msqrt>
    }

    if (command === 'text' || command === 'textrm' || command === 'mbox') {
      return <mtext key={this.nextKey('text')}>{textFromRawGroup(this.readRequiredRawGroup())}</mtext>
    }

    if (command === 'operatorname') {
      return <mi key={this.nextKey('operator-name')} mathVariant="normal">{textFromRawGroup(this.readRequiredRawGroup())}</mi>
    }

    if (command === 'mathbf' || command === 'boldsymbol') {
      return <mstyle key={this.nextKey('bold')} mathVariant="bold">{this.parseRequiredGroup()}</mstyle>
    }

    if (command === 'mathrm') {
      return <mstyle key={this.nextKey('roman')} mathVariant="normal">{this.parseRequiredGroup()}</mstyle>
    }

    if (command === 'mathit') {
      return <mstyle key={this.nextKey('italic')} mathVariant="italic">{this.parseRequiredGroup()}</mstyle>
    }

    if (command === 'mathbb') {
      return <mstyle key={this.nextKey('double-struck')} mathVariant="double-struck">{this.parseRequiredGroup()}</mstyle>
    }

    if (command === 'mathcal') {
      return <mstyle key={this.nextKey('script')} mathVariant="script">{this.parseRequiredGroup()}</mstyle>
    }

    if (command === 'mathfrak') {
      return <mstyle key={this.nextKey('fraktur')} mathVariant="fraktur">{this.parseRequiredGroup()}</mstyle>
    }

    if (command === 'underline') {
      return (
        <munder key={this.nextKey('underline')}>
          {this.parseRequiredGroup()}
          <mo>_</mo>
        </munder>
      )
    }

    if (ACCENT_COMMANDS[command]) {
      return (
        <mover key={this.nextKey('accent')} accent="true">
          {this.parseRequiredGroup()}
          <mo>{ACCENT_COMMANDS[command]}</mo>
        </mover>
      )
    }

    if (command === 'left' || command === 'right') {
      return <mo key={this.nextKey('delimiter')}>{this.readDelimiter()}</mo>
    }

    if (command === 'begin') return this.parseEnvironment()

    if (FUNCTION_COMMANDS.has(command)) {
      return <mi key={this.nextKey('function')} mathVariant="normal">{command}</mi>
    }

    if (SPACING_COMMANDS[command]) {
      return <mspace key={this.nextKey('space')} width={SPACING_COMMANDS[command]} />
    }

    if (SYMBOL_COMMANDS[command]) {
      const symbol = SYMBOL_COMMANDS[command]
      const large = ['∑', '∏', '∐', '∫', '∬', '∭', '∮', '⋃', '⋂', '⋁', '⋀'].includes(symbol)
      return <mo key={this.nextKey('symbol')} largeop={large ? 'true' : undefined}>{symbol}</mo>
    }

    if (DELIMITER_COMMANDS[command]) {
      return <mo key={this.nextKey('delimiter')}>{DELIMITER_COMMANDS[command]}</mo>
    }

    if (command === 'limits' || command === 'nolimits' || command === 'displaystyle' || command === 'textstyle') {
      return <mrow key={this.nextKey('style-marker')} />
    }

    if (command === ' ') return <mspace key={this.nextKey('space')} width="0.33em" />

    return <mtext key={this.nextKey('unknown-command')}>{`\\${command}`}</mtext>
  }

  private parseRequiredGroup(): ReactNode {
    this.skipWhitespace()
    if (this.peek() === '{') {
      this.index += 1
      return <mrow key={this.nextKey('required-group')}>{this.parseSequence('}')}</mrow>
    }
    return this.parseBase()
  }

  private readRequiredRawGroup(): string {
    this.skipWhitespace()
    if (this.peek() !== '{') return ''
    return this.readRawDelimited('{', '}')
  }

  private readOptionalRawGroup(): string | null {
    this.skipWhitespace()
    if (this.peek() !== '[') return null
    return this.readRawDelimited('[', ']')
  }

  private readRawDelimited(open: string, close: string): string {
    if (this.peek() !== open) return ''
    this.index += 1
    let depth = 1
    let value = ''

    while (this.index < this.source.length) {
      const char = this.peek()
      const previous = this.source[this.index - 1]
      this.index += 1

      if (char === open && previous !== '\\') {
        depth += 1
        value += char
        continue
      }

      if (char === close && previous !== '\\') {
        depth -= 1
        if (depth === 0) break
        value += char
        continue
      }

      value += char
    }

    return value
  }

  private readDelimiter(): string {
    this.skipWhitespace()
    if (this.peek() === '\\') {
      const command = this.readCommandName()
      return DELIMITER_COMMANDS[command] || SYMBOL_COMMANDS[command] || command
    }

    const delimiter = this.peek()
    if (delimiter) this.index += 1
    return delimiter === '.' ? '' : delimiter
  }

  private parseEnvironment(): ReactNode {
    const environment = this.readRequiredRawGroup()
    const closeToken = `\\end{${environment}}`
    const closeIndex = this.source.indexOf(closeToken, this.index)

    if (!environment || closeIndex < 0) {
      return <mtext key={this.nextKey('environment-fallback')}>{`\\begin{${environment}}`}</mtext>
    }

    const body = this.source.slice(this.index, closeIndex)
    this.index = closeIndex + closeToken.length

    const rows = splitTopLevel(body, '\\\\').map((row) => splitTopLevel(row, '&'))
    const table = (
      <mtable key={this.nextKey('matrix-table')}>
        {rows.map((row, rowIndex) => (
          <mtr key={`row-${rowIndex}`}>
            {row.map((cell, cellIndex) => (
              <mtd key={`cell-${rowIndex}-${cellIndex}`}>
                <mrow>{new LatexMathParser(cell.trim()).parseRoot()}</mrow>
              </mtd>
            ))}
          </mtr>
        ))}
      </mtable>
    )

    const fences: Record<string, [string, string]> = {
      matrix: ['', ''],
      aligned: ['', ''],
      pmatrix: ['(', ')'],
      bmatrix: ['[', ']'],
      Bmatrix: ['{', '}'],
      vmatrix: ['|', '|'],
      Vmatrix: ['‖', '‖'],
      cases: ['{', ''],
    }
    const [left, right] = fences[environment] || ['', '']

    return (
      <mrow key={this.nextKey('matrix')}>
        {left ? <mo>{left}</mo> : null}
        {table}
        {right ? <mo>{right}</mo> : null}
      </mrow>
    )
  }
}

function renderMath(expression: string): ReactNode {
  try {
    const nodes = new LatexMathParser(expression.trim()).parseRoot()
    return <mrow>{nodes}</mrow>
  } catch {
    return <mtext>{expression}</mtext>
  }
}

export function MathExpression({ expression, display = false, className }: MathExpressionProps) {
  const math = (
    <math
      aria-label={expression}
      display={display ? 'block' : 'inline'}
      className={cn('max-w-full text-white', display ? 'min-w-max text-[1.08em]' : 'text-[1.05em]')}
    >
      {renderMath(expression)}
    </math>
  )

  if (display) {
    return (
      <div
        className={cn(
          'my-3 max-w-full overflow-x-auto rounded-lg border border-border/80 bg-background/45 px-4 py-3 text-center',
          className,
        )}
        data-math-display="true"
        title={expression}
      >
        {math}
      </div>
    )
  }

  return (
    <span
      className={cn('mx-0.5 inline-flex max-w-full align-middle', className)}
      data-math-inline="true"
      title={expression}
    >
      {math}
    </span>
  )
}
