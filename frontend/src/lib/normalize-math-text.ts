export function normalizeMathText(input: string): string {
  let text = String(input ?? '');

  // Convert common "escaped newline" sequences into real newlines.
  // This helps when content arrives double-escaped via JSON.
  text = text.replace(/\\n/g, '\n');

  // Fix common double-escaped LaTeX delimiters and commands.
  // Example: "\\(x\\)" should become "\(x\)" so KaTeX auto-render can detect it.
  text = text
    .replace(/\\\\\[/g, '\\[')
    .replace(/\\\\\]/g, '\\]')
    .replace(/\\\\\(/g, '\\(')
    .replace(/\\\\\)/g, '\\)')
    .replace(/\\\\\{/g, '\\{')
    .replace(/\\\\\}/g, '\\}')
    .replace(/\\\\%/g, '\\%');

  // Fix a few common commands when they get double-escaped.
  // Keep this conservative to avoid breaking legitimate "\\" newlines in LaTeX.
  text = text.replace(/\\\\(frac|sqrt|begin|end|text|cdot|times|sum|int|alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|phi|omega)\b/g, '\\$1');

  return text;
}
