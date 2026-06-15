'use client';

import { memo, useEffect, useId, useMemo, useRef } from 'react';
import renderMathInElement from 'katex/contrib/auto-render';
import { normalizeMathText } from '@/lib/normalize-math-text';

/**
 * Inline math-aware text for SHORT strings — titles, headings, sidebar labels,
 * breadcrumbs. Unlike `MarkdownWithMath` (which is built for body content and
 * always wraps output in a block `<p class="md-p">` with `dir="rtl"` /
 * `text-right` / `leading-7`), this renders the string inline and only swaps in
 * KaTeX for the math spans, leaving the surrounding layout/typography to the
 * caller. That makes it safe inside a flex row, an accordion trigger, or an
 * `<h1>`/`<h2>` without invalid nesting or unwanted vertical spacing.
 *
 * LaTeX delimiters are normalized first (`normalizeMathText`) so double-escaped
 * forms like `\\(x\\)` still render. All math is forced INLINE (no display
 * blocks) so a stray `\[...\]` in a heading can't explode into a centered block.
 */
type MathTextProps = {
	text: string | null | undefined;
	className?: string;
	as?: 'span' | 'div';
};

function escapeHtml(text: string): string {
	return text
		.replaceAll('&', '&amp;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
		.replaceAll('"', '&quot;')
		.replaceAll("'", '&#39;');
}

// After normalization, math delimiters are `\(`, `\[`, `$` or `$$`.
const HAS_MATH = /\\\(|\\\[|\$/;

function MathTextImpl({ text, className, as = 'span' }: MathTextProps) {
	const containerRef = useRef<HTMLElement | null>(null);
	const uniqueId = useId();

	const normalized = useMemo(() => normalizeMathText(String(text ?? '')), [text]);
	const hasMath = useMemo(() => HAS_MATH.test(normalized), [normalized]);

	useEffect(() => {
		const el = containerRef.current;
		if (!el || !hasMath) return;

		const frame = requestAnimationFrame(() => {
			try {
				renderMathInElement(el, {
					delimiters: [
						// Titles are single-line: render every form INLINE.
						{ left: '\\[', right: '\\]', display: false },
						{ left: '\\(', right: '\\)', display: false },
						{ left: '$$', right: '$$', display: false },
						{ left: '$', right: '$', display: false },
					],
					throwOnError: false,
				});
			} catch {
				// ignore KaTeX failures — fall back to the escaped source text
			}
		});

		return () => cancelAnimationFrame(frame);
	}, [normalized, hasMath, uniqueId]);

	const Component = as as 'span' | 'div';

	// No math → let React own the text node (no dangerouslySetInnerHTML, no
	// KaTeX pass). This is the common case for static Persian labels.
	if (!hasMath) {
		return <Component className={className}>{normalized}</Component>;
	}

	// Math present → hand the DOM to KaTeX via dangerouslySetInnerHTML so its
	// mutations don't fight React's reconciler. The content-based key forces a
	// fresh element when the text changes.
	return (
		<Component
			key={`${uniqueId}-${normalized.slice(0, 64)}`}
			ref={containerRef as React.RefObject<HTMLSpanElement & HTMLDivElement>}
			className={className}
			// eslint-disable-next-line react/no-danger
			dangerouslySetInnerHTML={{ __html: escapeHtml(normalized) }}
		/>
	);
}

export const MathText = memo(
	MathTextImpl,
	(prev, next) => prev.text === next.text && prev.className === next.className && prev.as === next.as
);

MathText.displayName = 'MathText';
