'use client';

import { memo, useEffect, useId, useMemo, useRef } from 'react';
import renderMathInElement from 'katex/contrib/auto-render';

type MarkdownWithMathProps = {
	markdown: string;
	className?: string;
	renderKey?: string | number; // Force re-render when this changes
	as?: 'div' | 'span';
};

function escapeHtml(text: string): string {
	return text
		.replaceAll('&', '&amp;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
		.replaceAll('"', '&quot;')
		.replaceAll("'", '&#39;');
}

// Ported from transcripter-main/static/js/learn.js (formatMarkdown + tryRenderMath)
// with one safety tweak: we escape HTML outside of LaTeX/code to avoid injection.
function formatMarkdown(md: string): string {
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

	// ============ STEP 7: Links ============
	html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer" class="md-link">$1</a>');

	// ============ STEP 8: Paragraphs ============
	html = html.replace(/\n\n+/g, '</p><p class="md-p">');
	html = html.replace(/\n/g, '<br>');

	if (!html.startsWith('<h') && !html.startsWith('<ul') && !html.startsWith('<ol') && !html.startsWith('<pre') && !html.startsWith('<div')) {
		html = '<p class="md-p">' + html + '</p>';
	}

	html = html.replace(/<p class="md-p"><\/p>/g, '');
	html = html.replace(/<p class="md-p"><br>/g, '<p class="md-p">');

	// ============ STEP 9: Restore LaTeX ============
	html = html.replace(/%%LATEXBLOCK(\d+)%%/g, (_match, idx) => {
		const n = Number.parseInt(String(idx), 10);
		return `<div class="math-block" dir="ltr">$$${latexBlocks[n] ?? ''}$$</div>`;
	});

	html = html.replace(/%%LATEXINLINE(\d+)%%/g, (_match, idx) => {
		const n = Number.parseInt(String(idx), 10);
		return `<span class="math-inline" dir="ltr">$${latexInlines[n] ?? ''}$</span>`;
	});

	return html;
}

function MarkdownWithMathImpl({ markdown, className, renderKey, as }: MarkdownWithMathProps) {
	const containerRef = useRef<HTMLElement | null>(null);
	const uniqueId = useId();

	const html = useMemo(() => formatMarkdown(markdown || ''), [markdown]);

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
		prev.as === next.as
);

MarkdownWithMath.displayName = 'MarkdownWithMath';