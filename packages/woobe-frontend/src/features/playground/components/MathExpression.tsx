import { createElement, type ReactNode } from 'react'
import { MathSurface } from '@woobe/ui'

interface MathExpressionProps {
  expression: string
  display?: boolean
  className?: string
}

type MathProps = Record<string, unknown> | null

function mathNode(tag: string, props: MathProps, ...children: ReactNode[]): ReactNode {
  return createElement(tag, props, ...children)
}

const SYMBOL_COMMANDS: Record<string, string> = {
  alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', epsilon: 'ε', varepsilon: 'ϵ', zeta: 'ζ', eta: 'η',
  theta: 'θ', vartheta: 'ϑ', iota: 'ι', kappa: 'κ', lambda: 'λ', mu: 'μ', nu: 'ν', xi: 'ξ',
  omicron: 'ο', pi: 'π', varpi: 'ϖ', rho: 'ρ', varrho: 'ϱ', sigma: 'σ', varsigma: 'ς', tau: 'τ',
  upsilon: 'υ', phi: 'φ', varphi: 'ϕ', chi: 'χ', psi: 'ψ', omega: 'ω', Gamma: 'Γ', Delta: 'Δ',
  Theta: 'Θ', Lambda: 'Λ', Xi: 'Ξ', Pi: 'Π', Sigma: 'Σ', Upsilon: 'Υ', Phi: 'Φ', Psi: 'Ψ', Omega: 'Ω',
  infty: '∞', partial: '∂', nabla: '∇', ell: 'ℓ', hbar: 'ℏ', imath: 'ı', jmath: 'ȷ',
  sum: '∑', prod: '∏', coprod: '∐', int: '∫', iint: '∬', iiint: '∭', oint: '∮',
  bigcup: '⋃', bigcap: '⋂', bigvee: '⋁', bigwedge: '⋀',
  le: '≤', leq: '≤', ge: '≥', geq: '≥', neq: '≠', ne: '≠', approx: '≈', sim: '∼', simeq: '≃',
  equiv: '≡', propto: '∝', cong: '≅', to: '→', rightarrow: '→', leftarrow: '←', leftrightarrow: '↔',
  Rightarrow: '⇒', Leftarrow: '⇐', Leftrightarrow: '⇔', mapsto: '↦', hookrightarrow: '↪', hookleftarrow: '↩',
  uparrow: '↑', downarrow: '↓', updownarrow: '↕', times: '×', cdot: '⋅', ast: '∗', star: '⋆', div: '÷',
  pm: '±', mp: '∓', circ: '∘', bullet: '•', cap: '∩', cup: '∪', subset: '⊂', subseteq: '⊆',
  supset: '⊃', supseteq: '⊇', in: '∈', notin: '∉', ni: '∋', forall: '∀', exists: '∃', nexists: '∄',
  neg: '¬', land: '∧', wedge: '∧', lor: '∨', vee: '∨', angle: '∠', measuredangle: '∡', degree: '°',
  prime: '′', emptyset: '∅', varnothing: '∅', top: '⊤', bot: '⊥', parallel: '∥', perp: '⊥',
  ldots: '…', dots: '…', cdots: '⋯', vdots: '⋮', ddots: '⋱',
}

const DELIMITER_COMMANDS: Record<string, string> = {
  lbrace: '{', rbrace: '}', langle: '⟨', rangle: '⟩', lceil: '⌈', rceil: '⌉',
  lfloor: '⌊', rfloor: '⌋', vert: '|', Vert: '‖', backslash: '\\',
}

const FUNCTION_COMMANDS = new Set([
  'sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh',
  'log', 'ln', 'exp', 'lim', 'limsup', 'liminf', 'max', 'min', 'sup', 'inf', 'det', 'gcd', 'mod',
])

const SPACING_COMMANDS: Record<string, string> = {
  ',': '0.17em', ':': '0.22em', ';': '0.28em', '!': '-0.12em', quad: '1em', qquad: '2em',
  enspace: '0.5em', thinspace: '0.17em',
}

const ACCENT_COMMANDS: Record<string, string> = {
  hat: '^', widehat: '^', bar: '¯', overline: '¯', vec: '→', dot: '˙', ddot: '¨',
  tilde: '~', widetilde: '~', breve: '˘', check: 'ˇ',
}

const LARGE_OPERATORS = new Set(['∑', '∏', '∐', '∫', '∬', '∭', '∮', '⋃', '⋂', '⋁', '⋀'])

function textFromRawGroup(value: string): string {
  return value.replace(/\\([{}_$%&#])/g, '$1').replace(/~/g, ' ')
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

    if (subscript && superscript) return mathNode('msubsup', { key: this.nextKey('subsup') }, base, subscript, superscript)
    if (subscript) return mathNode('msub', { key: this.nextKey('sub') }, base, subscript)
    if (superscript) return mathNode('msup', { key: this.nextKey('sup') }, base, superscript)
    return base
  }

  private parseScriptArgument(): ReactNode {
    this.skipWhitespace()
    if (this.peek() === '{') {
      this.index += 1
      return mathNode('mrow', { key: this.nextKey('script-group') }, ...this.parseSequence('}'))
    }
    return this.parseBase()
  }

  private parseBase(): ReactNode {
    const char = this.peek()
    if (!char) return mathNode('mrow', { key: this.nextKey('empty') })

    if (char === '{') {
      this.index += 1
      return mathNode('mrow', { key: this.nextKey('group') }, ...this.parseSequence('}'))
    }
    if (char === '\\') return this.parseCommand()

    if (/[0-9]/.test(char)) {
      let value = ''
      while (/[0-9.,]/.test(this.peek())) {
        value += this.peek()
        this.index += 1
      }
      return mathNode('mn', { key: this.nextKey('number') }, value)
    }

    if (/[A-Za-zÀ-ÖØ-öø-ÿΑ-ω]/.test(char)) {
      this.index += 1
      return mathNode('mi', { key: this.nextKey('identifier') }, char)
    }

    this.index += 1
    return mathNode('mo', { key: this.nextKey('operator') }, char === '*' ? '⋅' : char)
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
      return mathNode('mfrac', { key: this.nextKey('fraction') }, this.parseRequiredGroup(), this.parseRequiredGroup())
    }

    if (command === 'binom') {
      const fraction = mathNode(
        'mfrac',
        { key: this.nextKey('binom-fraction'), linethickness: '0' },
        this.parseRequiredGroup(),
        this.parseRequiredGroup(),
      )
      return mathNode('mrow', { key: this.nextKey('binom') }, mathNode('mo', null, '('), fraction, mathNode('mo', null, ')'))
    }

    if (command === 'sqrt') {
      const optionalIndex = this.readOptionalRawGroup()
      const radicand = this.parseRequiredGroup()
      if (optionalIndex != null) {
        return mathNode(
          'mroot',
          { key: this.nextKey('root') },
          radicand,
          mathNode('mrow', null, ...new LatexMathParser(optionalIndex).parseRoot()),
        )
      }
      return mathNode('msqrt', { key: this.nextKey('sqrt') }, radicand)
    }

    if (command === 'text' || command === 'textrm' || command === 'mbox') {
      return mathNode('mtext', { key: this.nextKey('text') }, textFromRawGroup(this.readRequiredRawGroup()))
    }
    if (command === 'operatorname') {
      return mathNode('mi', { key: this.nextKey('operator-name'), mathvariant: 'normal' }, textFromRawGroup(this.readRequiredRawGroup()))
    }

    const styleVariants: Record<string, string> = {
      mathbf: 'bold', boldsymbol: 'bold', mathrm: 'normal', mathit: 'italic', mathbb: 'double-struck',
      mathcal: 'script', mathfrak: 'fraktur',
    }
    if (styleVariants[command]) {
      return mathNode('mstyle', { key: this.nextKey('style'), mathvariant: styleVariants[command] }, this.parseRequiredGroup())
    }

    if (command === 'underline') {
      return mathNode('munder', { key: this.nextKey('underline') }, this.parseRequiredGroup(), mathNode('mo', null, '_'))
    }
    if (ACCENT_COMMANDS[command]) {
      return mathNode(
        'mover',
        { key: this.nextKey('accent'), accent: 'true' },
        this.parseRequiredGroup(),
        mathNode('mo', null, ACCENT_COMMANDS[command]),
      )
    }

    if (command === 'left' || command === 'right') {
      return mathNode('mo', { key: this.nextKey('delimiter') }, this.readDelimiter())
    }
    if (command === 'begin') return this.parseEnvironment()
    if (FUNCTION_COMMANDS.has(command)) {
      return mathNode('mi', { key: this.nextKey('function'), mathvariant: 'normal' }, command)
    }
    if (SPACING_COMMANDS[command]) {
      return mathNode('mspace', { key: this.nextKey('space'), width: SPACING_COMMANDS[command] })
    }
    if (SYMBOL_COMMANDS[command]) {
      const symbol = SYMBOL_COMMANDS[command]
      return mathNode('mo', { key: this.nextKey('symbol'), largeop: LARGE_OPERATORS.has(symbol) ? 'true' : undefined }, symbol)
    }
    if (DELIMITER_COMMANDS[command]) {
      return mathNode('mo', { key: this.nextKey('delimiter') }, DELIMITER_COMMANDS[command])
    }
    if (command === 'limits' || command === 'nolimits' || command === 'displaystyle' || command === 'textstyle') {
      return mathNode('mrow', { key: this.nextKey('style-marker') })
    }
    if (command === ' ') return mathNode('mspace', { key: this.nextKey('space'), width: '0.33em' })
    return mathNode('mtext', { key: this.nextKey('unknown-command') }, `\\${command}`)
  }

  private parseRequiredGroup(): ReactNode {
    this.skipWhitespace()
    if (this.peek() === '{') {
      this.index += 1
      return mathNode('mrow', { key: this.nextKey('required-group') }, ...this.parseSequence('}'))
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
      return mathNode('mtext', { key: this.nextKey('environment-fallback') }, `\\begin{${environment}}`)
    }

    const body = this.source.slice(this.index, closeIndex)
    this.index = closeIndex + closeToken.length
    const rows = splitTopLevel(body, '\\\\').map((row) => splitTopLevel(row, '&'))
    const table = mathNode(
      'mtable',
      { key: this.nextKey('matrix-table') },
      ...rows.map((row, rowIndex) => mathNode(
        'mtr',
        { key: `row-${rowIndex}` },
        ...row.map((cell, cellIndex) => mathNode(
          'mtd',
          { key: `cell-${rowIndex}-${cellIndex}` },
          mathNode('mrow', null, ...new LatexMathParser(cell.trim()).parseRoot()),
        )),
      )),
    )

    const fences: Record<string, [string, string]> = {
      matrix: ['', ''], aligned: ['', ''], array: ['', ''], pmatrix: ['(', ')'], bmatrix: ['[', ']'],
      Bmatrix: ['{', '}'], vmatrix: ['|', '|'], Vmatrix: ['‖', '‖'], cases: ['{', ''],
    }
    const [left, right] = fences[environment] || ['', '']
    return mathNode(
      'mrow',
      { key: this.nextKey('matrix') },
      left ? mathNode('mo', null, left) : null,
      table,
      right ? mathNode('mo', null, right) : null,
    )
  }
}

function renderMath(expression: string): ReactNode {
  try {
    return mathNode('mrow', null, ...new LatexMathParser(expression.trim()).parseRoot())
  } catch {
    return mathNode('mtext', null, expression)
  }
}

export function MathExpression({ expression, display = false, className }: MathExpressionProps) {
  const math = mathNode(
    'math',
    {
      'aria-label': expression,
      display: display ? 'block' : 'inline',
      className: 'max-w-full',
    },
    renderMath(expression),
  )

  return (
    <MathSurface display={display} className={className} title={expression}>
      {math}
    </MathSurface>
  )
}
