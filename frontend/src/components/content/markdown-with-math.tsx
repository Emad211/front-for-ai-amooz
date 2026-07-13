'use client';

import { memo, useEffect, useId, useMemo, useRef } from 'react';
import renderMathInElement from 'katex/contrib/auto-render';

type MarkdownWithMathProps = {
	markdown: string;
	className?: string;
	renderKey?: string | number; // Force re-render when this changes
	as?: 'div' | 'span';
	allowImages?: boolean;
};

function escapeHtml(text: string): string {
	return text
		.replaceAll('&', '&amp;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
		.replaceAll('"', '&quot;')
		.replaceAll("'", '&#39;');
}

function unescapeMarkdownUrl(text: string): string {
	return String(text)
		.replaceAll('&amp;', '&')
		.replaceAll('&quot;', '"')
		.replaceAll('&#39;', "'");
}

// Backend (Django) serves extracted figure images at /media/...; the Next.js
// origin differs, so relative media URLs are resolved against the API base.
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/+$/, '');

function sanitizeMarkdownUrl(raw: string, { image = false }: { image?: boolean } = {}): string | null {
	const s = unescapeMarkdownUrl(raw).trim();
	if (!s || /[\u0000-\u001f\u007f]/.test(s)) return null;
	if (/^https?:\/\//i.test(s)) return s;
	if (s.startsWith('//')) return null;
	if (s.startsWith('/')) {
		if (image && API_BASE && s.startsWith('/media/')) return API_BASE + s;
		return s;
	}
	return null;
}

function resolveImgSrc(src: string): string | null {
	return sanitizeMarkdownUrl(src, { image: true });
}

// ---- GFM table support ------------------------------------------------------
function splitTableCells(line: string): string[] {
	const ESC = '@@PIPE@@';
	return line
		.trim()
		.replace(/^\|/, '')
		.replace(/\|$/, '')
		.replace(/\\\|/g, ESC)
		.split('|')
		.map((c) => c.split(ESC).join('|').trim());
}

function buildTableHtml(header: string, body: string[]): string {
	const head = splitTableCells(header)
		.map((c) => `<th>${escapeHtml(c)}</th>`)
		.join('');
	const rows = body
		.map(
			(r) =>
				`<tr>${splitTableCells(r)
					.map((c) => `<td>${escapeHtml(c)}</td>`)
					.join('')}</tr>`
		)
		.join('');
	return `<table class="md-table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`;
}

function protectTables(src: string, store: string[]): string {
	const lines = src.split('\n');
	const out: string[] = [];
	const isRow = (l: string) => /^\s*\|.*\|\s*$/.test(l);
	const isSep = (l: string) => /^\s*\|(\s*:?-+:?\s*\|)+\s*$/.test(l);
	let i = 0;
	while (i < lines.length) {
		if (isRow(lines[i]) && i + 1 < lines.length && isSep(lines[i + 1])) {
			const header = lines[i];
			const body: string[] = [];
			let j = i + 2;
			while (j < lines.length && isRow(lines[j])) {
				body.push(lines[j]);
				j++;
			}
			store.push(buildTableHtml(header, body));
			out.push(`%%TABLEBLOCK${store.length - 1}%%`);
			i = j;
		} else {
			out.push(lines[i]);
			i++;
		}
	}
	return out.join('\n');
}

// Ported from transcripter-main/static/js/learn.js (formatMarkdown + tryRenderMath)
// with one safety tweak: we escape HTML outside of LaTeX/code to avoid injection.
function formatMarkdown(md: string, allowImages = true): string {
	if (!md) return '';

	let html = String(md)
		// Repair common LaTeX commands that break when embedded in JSON strings.
		// Example: "\text" can become "<TAB>ext" after JSON parsing.
		.replaceAll('\t', '\\t')
		.replaceAll('\b', '\\b')
		.replaceAll('\f', '\\f');

	// ============ STEP 1: Protect LaTeX from processing ============
	const latexBlocks: string[] = [];
	const latexInlines: string[] = [];

	// Protect block LaTeX \\[...\\]
	html = html.replace(/\\\[([\s\S]*?)\\\]/g, (_match, content) => {
		latexBlocks.push(String(content));
		return `%%LATEXBLOCK${latexBlocks.length - 1}%%`;
	});

	// Protect inline LaTeX \\(...\\)
	html = html.replace(/\\\(([\s\S]*?)\\\)/g, (_match, content) => {
		latexInlines.push(String(content));
		return `%%LATEXINLINE${latexInlines.length - 1}%%`;
	});

	// Protect block LaTeX $$...$$
	html = html.replace(/\$\$([\s\S]*?)\$\$/g, (_match, content) => {
		latexBlocks.push(String(content));
		return `%%LATEXBLOCK${latexBlocks.length - 1}%%`;
	});

	// Protect inline LaTeX $...$
	html = html.replace(/\$([^\n$]+?)\$/g, (_match, content) => {
		latexInlines.push(String(content));
		return `%%LATEXINLINE${latexInlines.length - 1}%%`;
	});

	// ============ STEP 1b: Protect GFM tables (built before escaping) ============
	// Cell text may contain %%LATEXINLINE..%% placeholders — those survive and are
	// restored after the table HTML is re-inserted (see STEP 9).
	const tableBlocks: string[] = [];
	html = protectTables(html, tableBlocks);

	// ============ STEP 2: Code blocks ============
	function looksLikeLatex(s: string): boolean {
		if (!s) return false;
		return /\\/.test(s) || /[{}]/.test(s) || /\^|_/.test(s) || /\\?frac|\\?begin|\\?alpha|\\?beta/.test(s);
	}

	// Triple-backtick blocks: if they look like LaTeX, protect them as LaTeX blocks
	html = html.replace(/```([\s\S]*?)```/g, (_m, content) => {
		const raw = String(content);
		if (looksLikeLatex(raw)) {
			latexBlocks.push(raw.trim());
			return `%%LATEXBLOCK${latexBlocks.length - 1}%%`;
		}
		return `<pre class="md-pre"><code>${escapeHtml(raw)}</code></pre>`;
	});

	// Inline code: if it contains LaTeX, treat as inline math so KaTeX will render it
	html = html.replace(/`([^`]+)`/g, (_m, content) => {
		const raw = String(content);
		if (looksLikeLatex(raw)) {
			latexInlines.push(raw.trim());
			return `%%LATEXINLINE${latexInlines.length - 1}%%`;
		}
		return `<code class="inline-code">${escapeHtml(raw)}</code>`;
	});

	// Escape HTML in the remainder to avoid script injection.
	html = escapeHtml(html);

	// ============ STEP 3: Headers ============
	html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>');
	html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>');
	html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>');
	html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>');

	// ============ STEP 4: Bold & Italic ============
	html = html.replace(/\*\*\*([\s\S]+?)\*\*\*/g, '<strong><em>$1</em></strong>');
	html = html.replace(/\*\*([\s\S]+?)\*\*/g, '<strong>$1</strong>');
	html = html.replace(/__([\s\S]+?)__/g, '<strong>$1</strong>');
	html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
	// NOTE: _.._ italic intentionally omitted — conflicts with LaTeX subscripts (x_1).

	// ============ STEP 5: Lists ============
	html = html.replace(/^[\*\-•]\s+(.+)$/gm, '<li class="md-li">$1</li>');
	html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li class="md-li-num" value="$1">$2</li>');
	html = html.replace(/(<li class="md-li">[\s\S]*?<\/li>)+/g, '<ul class="md-ul">$&</ul>');
	html = html.replace(/(<li class="md-li-num"[^>]*>[\s\S]*?<\/li>)+/g, '<ol class="md-ol">$&</ol>');

	// ============ STEP 6: Horizontal rule ============
	html = html.replace(/^---+$/gm, '<hr class="md-hr">');
	html = html.replace(/^\*\*\*+$/gm, '<hr class="md-hr">');

	// ============ STEP 6b: Images (MUST run before links) ============
	// ![alt](src) → <img>. Relative /media/... srcs resolve to the backend.
	html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_m, alt, src) => {
		if (!allowImages) return String(alt);
		const safeSrc = resolveImgSrc(src);
		if (!safeSrc) return '';
		return `<img src="${escapeHtml(safeSrc)}" alt="${escapeHtml(String(alt))}" class="md-img" loading="lazy" />`;
	});

	// ============ STEP 7: Links ============
	html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, label, href) => {
		const safeHref = sanitizeMarkdownUrl(href);
		if (!safeHref) return String(label);
		return `<a href="${escapeHtml(safeHref)}" target="_blank" rel="noreferrer" class="md-link">${label}</a>`;
	});

	// ============ STEP 8: Paragraphs ============
	html = html.replace(/\n\n+/g, '</p><p class="md-p">');
	html = html.replace(/\n/g, '<br>');

	if (!html.startsWith('<h') && !html.startsWith('<ul') && !html.startsWith('<ol') && !html.startsWith('<pre') && !html.startsWith('<div')) {
		html = '<p class="md-p">' + html + '</p>';
	}

	html = html.replace(/<p class="md-p"><\/p>/g, '');
	html = html.replace(/<p class="md-p"><br>/g, '<p class="md-p">');

	// ============ STEP 9: Restore tables (before LaTeX so cell math resolves) ============
	html = html.replace(/%%TABLEBLOCK(\d+)%%/g, (_match, idx) => {
		const n = Number.parseInt(String(idx), 10);
		return tableBlocks[n] ?? '';
	});
	// Unwrap a lone table accidentally wrapped in a paragraph (invalid nesting).
	html = html.replace(/<p class="md-p">\s*(<table[\s\S]*?<\/table>)\s*<\/p>/g, '$1');

	// ============ STEP 9b: Restore LaTeX ============
	html = html.replace(/%%LATEXBLOCK(\d+)%%/g, (_match, idx) => {
		const n = Number.parseInt(String(idx), 10);
		return `<div class="math-block" dir="ltr">$$${escapeHtml(latexBlocks[n] ?? '')}$$</div>`;
	});

	html = html.replace(/%%LATEXINLINE(\d+)%%/g, (_match, idx) => {
		const n = Number.parseInt(String(idx), 10);
		return `<span class="math-inline" dir="ltr">$${escapeHtml(latexInlines[n] ?? '')}$</span>`;
	});

	return html;
}

function MarkdownWithMathImpl({ markdown, className, renderKey, as, allowImages = true }: MarkdownWithMathProps) {
	const containerRef = useRef<HTMLElement | null>(null);
	const uniqueId = useId();

	const html = useMemo(() => formatMarkdown(markdown || '', allowImages), [markdown, allowImages]);

	// Run KaTeX render after DOM update
	useEffect(() => {
		const el = containerRef.current;
		if (!el) return;

		// Use requestAnimationFrame to ensure DOM is painted first
		const frame = requestAnimationFrame(() => {
			try {
				renderMathInElement(el, {
					delimiters: [
						{ left: '\\[', right: '\\]', display: true },
						{ left: '\\(', right: '\\)', display: false },
						{ left: '$$', right: '$$', display: true },
						{ left: '$', right: '$', display: false },
					],
					throwOnError: false,
				});
			} catch {
				// ignore KaTeX failures
			}
		});

		return () => cancelAnimationFrame(frame);
	}, [html, renderKey, uniqueId]);

	// Generate a stable key for re-render based on content
	const contentKey = `${uniqueId}-${renderKey ?? ''}-${markdown?.slice(0, 50) ?? ''}`;
	const Component = (as ?? 'div') as any;

	return (
		<Component
			key={contentKey}
			ref={containerRef}
			dir="rtl"
			className={['text-right leading-7', className].filter(Boolean).join(' ')}
			// eslint-disable-next-line react/no-danger
			dangerouslySetInnerHTML={{ __html: html }}
		/>
	);
}

export const MarkdownWithMath = memo(
	MarkdownWithMathImpl,
	(prev, next) =>
		prev.markdown === next.markdown &&
		prev.className === next.className &&
		prev.renderKey === next.renderKey &&
		prev.as === next.as &&
		prev.allowImages === next.allowImages
);

MarkdownWithMath.displayName = 'MarkdownWithMath';
