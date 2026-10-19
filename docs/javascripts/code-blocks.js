(() => {
  function colourColumns(code, separator) {
    const text = code.textContent;
    const ranges = [];
    let start = 0;
    let column = 0;
    let quoted = false;

    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      if (char === '"') {
        if (quoted && text[index + 1] === '"') {
          index += 1;
        } else {
          quoted = !quoted;
        }
      }
      if (!quoted && (char === separator || char === "\n" || char === "\r")) {
        if (index > start) {
          ranges.push({ start, end: index, style: `code-column-${column % 7}` });
        }
        const newline = char !== separator;
        if (char === "\r" && text[index + 1] === "\n") {
          index += 1;
        }
        column = newline ? 0 : column + 1;
        start = index + 1;
      }
    }
    if (start < text.length) {
      ranges.push({ start, end: text.length, style: `code-column-${column % 7}` });
    }
    applyRanges(code, ranges);
  }

  function colourShell(code) {
    const text = code.textContent;
    const ranges = [];
    for (const match of text.matchAll(/^[ \t]*([A-Za-z0-9_][\w.-]*)|(?:^|[ \t])(--?[A-Za-z][\w-]*)/gm)) {
      const token = match[1] || match[2];
      const start = match.index + match[0].length - token.length;
      ranges.push({ start, end: start + token.length, style: match[1] ? "shell-command" : "shell-option" });
    }
    applyRanges(code, ranges, true);
  }

  function applyRanges(code, ranges, preserveTokens = false) {
    // Keep line anchors, and preserve Pygments' shell strings and comments.
    const walker = document.createTreeWalker(code, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    let offset = 0;
    for (const node of nodes) {
      const start = offset;
      offset += node.textContent.length;
      const token = node.parentElement.closest("span[class]");
      if (preserveTokens && token && !token.classList.contains("w")) continue;
      const matches = ranges.filter((range) => range.end > start && range.start < offset);
      if (!matches.length) continue;

      const fragment = document.createDocumentFragment();
      let cursor = 0;
      for (const range of matches) {
        const begin = Math.max(range.start, start) - start;
        const end = Math.min(range.end, offset) - start;
        fragment.append(node.textContent.slice(cursor, begin));
        const span = document.createElement("span");
        span.className = range.style;
        span.textContent = node.textContent.slice(begin, end);
        fragment.append(span);
        cursor = end;
      }
      fragment.append(node.textContent.slice(cursor));
      node.replaceWith(fragment);
    }
  }

  function highlightCodeBlocks() {
    document.querySelectorAll(".language-csv code, .language-tsv code").forEach((code) => {
      if (code.dataset.columnsColoured) return;
      colourColumns(code, code.closest(".language-tsv") ? "\t" : ",");
      code.dataset.columnsColoured = "true";
    });
    document.querySelectorAll(".language-shell code, .language-bash code, .language-sh code").forEach((code) => {
      if (code.dataset.shellColoured) return;
      colourShell(code);
      code.dataset.shellColoured = "true";
    });
  }

  if (typeof document$ !== "undefined") {
    document$.subscribe(highlightCodeBlocks);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", highlightCodeBlocks);
  } else {
    highlightCodeBlocks();
  }
})();
