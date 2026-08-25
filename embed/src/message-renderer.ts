import type { ResponseRenderMode } from "./appearance";

function appendTextWithBreaks(parent: Node, value: string) {
  const parts = value.split("\n");
  parts.forEach((part, index) => {
    if (part) parent.appendChild(document.createTextNode(part));
    if (index < parts.length - 1) parent.appendChild(document.createElement("br"));
  });
}

function appendInline(parent: HTMLElement, text: string, depth = 0) {
  if (depth > 4) {
    appendTextWithBreaks(parent, text);
    return;
  }

  const pattern = /(\[([^\]]+)\]\((https?:\/\/[^)\s]+)\))|(`([^`]+)`)|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)|(https?:\/\/[^\s<]+)/g;
  let lastIndex = 0;

  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    appendTextWithBreaks(parent, text.slice(lastIndex, start));

    if (match[1] && match[2] && match[3]) {
      const anchor = document.createElement("a");
      anchor.href = match[3];
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      appendInline(anchor, match[2], depth + 1);
      parent.append(anchor);
    } else if (match[5]) {
      const code = document.createElement("code");
      code.textContent = match[5];
      parent.append(code);
    } else if (match[7]) {
      const strong = document.createElement("strong");
      appendInline(strong, match[7], depth + 1);
      parent.append(strong);
    } else if (match[9]) {
      const emphasis = document.createElement("em");
      appendInline(emphasis, match[9], depth + 1);
      parent.append(emphasis);
    } else if (match[10]) {
      const anchor = document.createElement("a");
      anchor.href = match[10];
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.textContent = match[10];
      parent.append(anchor);
    }

    lastIndex = start + match[0].length;
  }

  appendTextWithBreaks(parent, text.slice(lastIndex));
}

function isHorizontalRule(line: string): boolean {
  return /^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line);
}

function splitTableCells(line: string): string[] {
  const value = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  const cells: string[] = [];
  let current = "";

  for (let index = 0; index < value.length; index += 1) {
    const char = value[index];
    const next = value[index + 1];
    if (char === "\\" && next === "|") {
      current += "|";
      index += 1;
      continue;
    }
    if (char === "|") {
      cells.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }

  cells.push(current.trim());
  return cells;
}

function tableAlignment(line: string, columns: number): Array<"left" | "center" | "right"> | null {
  if (!line.includes("|")) return null;
  const cells = splitTableCells(line);
  if (cells.length !== columns) return null;

  const result: Array<"left" | "center" | "right"> = [];
  for (const rawCell of cells) {
    const cell = rawCell.replace(/\s/g, "");
    if (!/^:?-{3,}:?$/.test(cell)) return null;
    const left = cell.startsWith(":");
    const right = cell.endsWith(":");
    result.push(left && right ? "center" : right ? "right" : "left");
  }
  return result;
}

function isBlockStart(lines: string[], index: number): boolean {
  const line = lines[index] ?? "";
  if (!line.trim()) return true;
  if (/^\s*```/.test(line)) return true;
  if (/^#{1,3}\s+/.test(line)) return true;
  if (/^\s*[-*+]\s+/.test(line)) return true;
  if (/^\s*\d+[.)]\s+/.test(line)) return true;
  if (isHorizontalRule(line)) return true;
  if (line.includes("|") && tableAlignment(lines[index + 1] ?? "", splitTableCells(line).length)) return true;
  return false;
}

function renderRich(target: HTMLElement, content: string) {
  const fragment = document.createDocumentFragment();
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const fence = line.match(/^\s*```\s*([\w-]+)?\s*$/);
    if (fence) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      if (fence[1]) code.dataset.language = fence[1];
      code.textContent = codeLines.join("\n");
      pre.append(code);
      fragment.append(pre);
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      const element = document.createElement(`h${heading[1].length}`);
      appendInline(element, heading[2]);
      fragment.append(element);
      index += 1;
      continue;
    }

    if (isHorizontalRule(line)) {
      fragment.append(document.createElement("hr"));
      index += 1;
      continue;
    }

    const headers = line.includes("|") ? splitTableCells(line) : [];
    const alignments = headers.length >= 2
      ? tableAlignment(lines[index + 1] ?? "", headers.length)
      : null;
    if (alignments) {
      const wrapper = document.createElement("div");
      wrapper.className = "message-table";
      const table = document.createElement("table");
      const thead = document.createElement("thead");
      const headerRow = document.createElement("tr");
      headers.forEach((header, column) => {
        const cell = document.createElement("th");
        cell.style.textAlign = alignments[column];
        appendInline(cell, header);
        headerRow.append(cell);
      });
      thead.append(headerRow);
      table.append(thead);

      const tbody = document.createElement("tbody");
      index += 2;
      while (index < lines.length && lines[index].includes("|")) {
        const cells = splitTableCells(lines[index]);
        if (cells.length !== headers.length) break;
        const row = document.createElement("tr");
        cells.forEach((value, column) => {
          const cell = document.createElement("td");
          cell.style.textAlign = alignments[column];
          appendInline(cell, value);
          row.append(cell);
        });
        tbody.append(row);
        index += 1;
      }
      table.append(tbody);
      wrapper.append(table);
      fragment.append(wrapper);
      continue;
    }

    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      const list = document.createElement(ordered ? "ol" : "ul");
      while (index < lines.length) {
        const itemMatch = ordered
          ? lines[index].match(/^\s*\d+[.)]\s+(.+)$/)
          : lines[index].match(/^\s*[-*+]\s+(.+)$/);
        if (!itemMatch) break;
        const item = document.createElement("li");
        appendInline(item, itemMatch[1]);
        list.append(item);
        index += 1;
      }
      fragment.append(list);
      continue;
    }

    const paragraphLines = [line];
    index += 1;
    while (index < lines.length && !isBlockStart(lines, index)) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    const paragraph = document.createElement("p");
    appendInline(paragraph, paragraphLines.join("\n"));
    fragment.append(paragraph);
  }

  target.replaceChildren(fragment);
}

export function renderMessageContent(
  target: HTMLElement,
  content: string,
  mode: ResponseRenderMode,
) {
  if (mode === "plain") {
    target.textContent = content;
    return;
  }
  renderRich(target, content);
}
