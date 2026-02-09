import logging
import os
import re
from typing import Any, Dict, Optional

import markdown

logger = logging.getLogger(__name__)


def get_font_path() -> str:
    """Find the best available Persian font for PDF generation.

    Search order:
    1. Bundled static font (project repo)
    2. System font installed via Dockerfile (Linux / Docker production)
    3. Common Linux font paths
    4. Windows fallbacks (local dev only)
    """
    paths = [
        # Project-bundled font
        os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "Vazirmatn-Regular.ttf"),
        os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "Vazirmatn.ttf"),
        # Docker / Linux system font (installed by Dockerfile)
        "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Regular.ttf",
        "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Bold.ttf",
        # Common Linux font paths
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        # Windows local development
        "C:/Windows/Fonts/Vazirmatn-Regular.ttf",
        "C:/Windows/Fonts/IRANSans.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            logger.info("PDF font found: %s", p)
            return p.replace("\\", "/")
    logger.warning("No Persian font found — PDF text may render incorrectly!")
    return ""


def get_bold_font_path() -> str:
    """Find bold variant of the Persian font (optional)."""
    paths = [
        os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "Vazirmatn-Bold.ttf"),
        "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Bold.ttf",
        "C:/Windows/Fonts/Vazirmatn-Bold.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return p.replace("\\", "/")
    return ""


def get_base_css(font_path: str) -> str:
    font_face = ""
    font_family = "sans-serif"

    if font_path:
        font_family = "MyPersianFont, Vazirmatn, Tahoma, sans-serif"
        bold_path = get_bold_font_path()
        font_face = f"""
        @font-face {{
            font-family: 'MyPersianFont';
            src: url('file://{font_path}');
            font-weight: normal;
            font-style: normal;
        }}
        """
        if bold_path:
            font_face += f"""
        @font-face {{
            font-family: 'MyPersianFont';
            src: url('file://{bold_path}');
            font-weight: bold;
            font-style: normal;
        }}
        """

    return f"""
    {font_face}

    @page {{
        size: A4;
        margin: 2.5cm;
        @bottom-center {{
            content: "صفحه " counter(page);
            font-family: {font_family};
            font-size: 10pt;
        }}
    }}

    body {{
        font-family: {font_family};
        direction: rtl;
        text-align: justify;
        line-height: 1.6;
        font-size: 12pt;
    }}

    h1, h2, h3 {{
        font-weight: bold;
        margin-top: 1.5em;
        margin-bottom: 0.5em;
    }}

    h1 {{ font-size: 24pt; text-align: center; color: #2c3e50; }}
    h2 {{ font-size: 18pt; border-bottom: 2px solid #eee; padding-bottom: 10px; color: #34495e; }}
    h3 {{ font-size: 14pt; color: #7f8c8d; }}

    img {{
        max-width: 100%;
        height: auto;
        display: block;
        margin: 1cm auto;
        border: 1px solid #ddd;
        border-radius: 4px;
    }}

    ul, ol {{ margin-right: 20px; }}

    /* Math / inline math styling (rendered as Unicode or fallback text) */
    .math-block {{
        text-align: center;
        direction: ltr;
        margin: 16px 0;
        padding: 8px;
    }}

    .math-inline {{
        direction: ltr;
        display: inline;
    }}

    .toc-item {{ margin-bottom: 5px; }}
    .toc-subitem {{ margin-right: 20px; font-size: 11pt; color: #555; }}
    .page-break {{ break-before: page; }}
    .cover-page {{ text-align: center; padding-top: 5cm; }}
    .footer-note {{ margin-top: 2cm; font-size: 10pt; color: #888; text-align: center; }}
    """


def clean_title_latex(title: str) -> str:
    if not title:
        return title
    result = title
    result = re.sub(r"\$\$(.+?)\$\$", r"\1", result)
    result = re.sub(r"\$([^$]+)\$", r"\1", result)
    result = result.replace(r"\\frac", "")
    result = result.replace(r"\\sqrt", "√")
    result = result.replace(r"\\times", "×")
    result = result.replace(r"\\div", "÷")
    result = re.sub(r"\\([a-zA-Z]+)", r"\1", result)
    result = result.replace("{", "").replace("}", "")
    return result.strip()


def format_chem(text: str) -> str:
    if not text:
        return ""
    sub = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉"}
    sup = {"+": "⁺", "-": "⁻", "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}

    def repl_sub(m):
        return m.group(1) + "".join(sub.get(c, c) for c in m.group(2))

    text = re.sub(r"([A-Z][a-z]?)(\d+)(?![spdfo])", repl_sub, text)

    def repl_sup(m):
        return "".join(sup.get(c, c) for c in m.group(1))

    text = re.sub(r"\^\\{?(\d*[+\-])\\}?", repl_sup, text)
    return text


def convert_latex_to_unicode(text: str) -> str:
    if not text:
        return text

    subscripts = {
        "0": "₀",
        "1": "₁",
        "2": "₂",
        "3": "₃",
        "4": "₄",
        "5": "₅",
        "6": "₆",
        "7": "₇",
        "8": "₈",
        "9": "₉",
        "a": "ₐ",
        "e": "ₑ",
        "h": "ₕ",
        "i": "ᵢ",
        "j": "ⱼ",
        "k": "ₖ",
        "l": "ₗ",
        "m": "ₘ",
        "n": "ₙ",
        "o": "ₒ",
        "p": "ₚ",
        "r": "ᵣ",
        "s": "ₛ",
        "t": "ₜ",
        "u": "ᵤ",
        "v": "ᵥ",
        "x": "ₓ",
        "+": "₊",
        "-": "₋",
        "=": "₌",
        "(": "₍",
        ")": "₎",
    }
    superscripts = {
        "0": "⁰",
        "1": "¹",
        "2": "²",
        "3": "³",
        "4": "⁴",
        "5": "⁵",
        "6": "⁶",
        "7": "⁷",
        "8": "⁸",
        "9": "⁹",
        "+": "⁺",
        "-": "⁻",
        "=": "⁼",
        "(": "⁽",
        ")": "⁾",
        "n": "ⁿ",
        "i": "ⁱ",
        "a": "ᵃ",
        "b": "ᵇ",
        "c": "ᶜ",
        "d": "ᵈ",
        "e": "ᵉ",
        "f": "ᶠ",
        "g": "ᵍ",
        "h": "ʰ",
        "j": "ʲ",
        "k": "ᵏ",
        "l": "ˡ",
        "m": "ᵐ",
        "o": "ᵒ",
        "p": "ᵖ",
        "r": "ʳ",
        "s": "ˢ",
        "t": "ᵗ",
        "u": "ᵘ",
        "v": "ᵛ",
        "w": "ʷ",
        "x": "ˣ",
        "y": "ʸ",
        "z": "ᶻ",
    }

    def extract_brace_content(s: str, start_pos: int):
        if start_pos >= len(s) or s[start_pos] != "{":
            return None, start_pos
        depth = 0
        content_start = start_pos + 1
        for i in range(start_pos, len(s)):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    return s[content_start:i], i + 1
        return None, start_pos

    def replace_command_with_braces(text_: str, cmd: str, formatter):
        out = []
        i = 0
        cmd_pattern = "\\" + cmd + "{"
        while i < len(text_):
            pos = text_.find(cmd_pattern, i)
            if pos == -1:
                out.append(text_[i:])
                break
            out.append(text_[i:pos])
            brace_start = pos + len(cmd_pattern) - 1
            content, end_pos = extract_brace_content(text_, brace_start)
            if content is not None:
                out.append(formatter(content))
                i = end_pos
            else:
                out.append(text_[pos : pos + len(cmd_pattern)])
                i = pos + len(cmd_pattern)
        return "".join(out)

    def replace_frac(text_: str) -> str:
        result_parts = []
        i = 0
        frac_pattern = "\\frac{"
        while i < len(text_):
            pos = text_.find(frac_pattern, i)
            if pos == -1:
                result_parts.append(text_[i:])
                break
            result_parts.append(text_[i:pos])
            brace_start = pos + len(frac_pattern) - 1
            num, num_end = extract_brace_content(text_, brace_start)
            if num is None:
                result_parts.append(text_[pos : pos + len(frac_pattern)])
                i = pos + len(frac_pattern)
                continue
            den, den_end = extract_brace_content(text_, num_end)
            if den is None:
                result_parts.append(f"({num})/")
                i = num_end
                continue
            if len(num) == 1 and len(den) == 1:
                result_parts.append(f"{num}/{den}")
            elif (
                len(num) <= 2
                and num.lstrip("-").replace(" ", "").isalnum()
                and len(den) <= 2
                and den.isalnum()
            ):
                result_parts.append(f"{num}/{den}")
            else:
                result_parts.append(f"({num})/({den})")
            i = den_end
        return "".join(result_parts)

    def latex_to_unicode(latex: str) -> str:
        result = latex.strip()
        result = replace_command_with_braces(result, "boxed", lambda c: f"[{c}]")
        result = replace_command_with_braces(result, "text", lambda c: f" {c} ")
        result = replace_command_with_braces(result, "sqrt", lambda c: f"√({c})")

        for _ in range(5):
            new_result = replace_frac(result)
            if new_result == result:
                break
            result = new_result

        result = result.replace(r"\implies", " ⟹ ")
        result = result.replace(r"\Rightarrow", " ⇒ ")
        result = result.replace(r"\rightarrow", " → ")
        result = result.replace(r"\leftarrow", " ← ")
        result = result.replace(r"\Leftarrow", " ⇐ ")
        result = result.replace(r"\leftrightarrow", " ↔ ")
        result = result.replace(r"\iff", " ⟺ ")

        symbol_replacements = [
            (r"\pm", "±"),
            (r"\mp", "∓"),
            (r"\times", "×"),
            (r"\div", "÷"),
            (r"\cdot", "·"),
            (r"\alpha", "α"),
            (r"\beta", "β"),
            (r"\gamma", "γ"),
            (r"\delta", "δ"),
            (r"\epsilon", "ε"),
            (r"\varepsilon", "ε"),
            (r"\theta", "θ"),
            (r"\lambda", "λ"),
            (r"\mu", "μ"),
            (r"\pi", "π"),
            (r"\sigma", "σ"),
            (r"\omega", "ω"),
            (r"\phi", "φ"),
            (r"\psi", "ψ"),
            (r"\Delta", "Δ"),
            (r"\Sigma", "Σ"),
            (r"\Omega", "Ω"),
            (r"\Pi", "Π"),
            (r"\Gamma", "Γ"),
            (r"\infty", "∞"),
            (r"\neq", "≠"),
            (r"\leq", "≤"),
            (r"\geq", "≥"),
            (r"\le", "≤"),
            (r"\ge", "≥"),
            (r"\approx", "≈"),
            (r"\equiv", "≡"),
            (r"\sim", "∼"),
            (r"\propto", "∝"),
            (r"\sum", "∑"),
            (r"\prod", "∏"),
            (r"\int", "∫"),
            (r"\partial", "∂"),
            (r"\nabla", "∇"),
            (r"\forall", "∀"),
            (r"\exists", "∃"),
            (r"\in", "∈"),
            (r"\notin", "∉"),
            (r"\subset", "⊂"),
            (r"\supset", "⊃"),
            (r"\cup", "∪"),
            (r"\cap", "∩"),
            (r"\emptyset", "∅"),
            (r"\varnothing", "∅"),
            (r"\left", ""),
            (r"\right", ""),
            (r"\,", " "),
            (r"\;", " "),
            (r"\:", " "),
            (r"\ ", " "),
            (r"\quad", "  "),
            (r"\qquad", "    "),
            (r"\mathrm", ""),
            (r"\mathbf", ""),
            (r"\mathit", ""),
            (r"\mathsf", ""),
            (r"\ldots", "…"),
            (r"\cdots", "⋯"),
            (r"\vdots", "⋮"),
            (r"\perp", "⊥"),
            (r"\parallel", "∥"),
            (r"\angle", "∠"),
        ]
        for cmd, replacement in symbol_replacements:
            result = result.replace(cmd, replacement)

        def replace_superscript(match):
            content = match.group(1)
            return "".join(superscripts.get(c, c) for c in content)

        result = re.sub(r"\^\{([^{}]+)\}", replace_superscript, result)
        result = re.sub(r"\^([0-9a-zA-Z])", lambda m: superscripts.get(m.group(1), "^" + m.group(1)), result)

        def replace_subscript(match):
            content = match.group(1)
            return "".join(subscripts.get(c, c) for c in content)

        result = re.sub(r"_\{([^{}]+)\}", replace_subscript, result)
        result = re.sub(r"_([0-9a-zA-Z])", lambda m: subscripts.get(m.group(1), "_" + m.group(1)), result)

        result = result.replace("{", "").replace("}", "")
        result = re.sub(r" +", " ", result)
        return result.strip()

    def convert_display_math(match):
        latex_content = match.group(1).strip()
        if not latex_content:
            return match.group(0)
        try:
            unicode_math = latex_to_unicode(latex_content)
            return f"<div class=\"math-block\">{unicode_math}</div>"
        except Exception as e:
            logger.warning("LaTeX display conversion failed: %s... - %s", latex_content[:50], e)
            return f"<div class=\"math-block\">{latex_content}</div>"

    def convert_inline_math(match):
        latex_content = match.group(1).strip()
        if not latex_content:
            return match.group(0)
        try:
            unicode_math = latex_to_unicode(latex_content)
            return f"<span class=\"math-inline\">{unicode_math}</span>"
        except Exception as e:
            logger.warning("LaTeX inline conversion failed: %s... - %s", latex_content[:30], e)
            return f"<span class=\"math-inline\">{latex_content}</span>"

    text = re.sub(r"\$\$(.+?)\$\$", convert_display_math, text, flags=re.DOTALL)
    text = re.sub(r"(?<!\$)\$([^$\n]+?)\$(?!\$)", convert_inline_math, text)
    return text


def process_content_to_html(markdown_text: str) -> str:
    if not markdown_text:
        return ""
    text = convert_latex_to_unicode(markdown_text)
    text = format_chem(text)
    return markdown.markdown(text, extensions=["extra", "nl2br"])


def generate_course_pdf(*, structure: Dict[str, Any], meta: Dict[str, Any], base_url: str) -> Optional[bytes]:
    """Generate a full-course PDF from a structure dict similar to the legacy Flask project."""
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration

        font_path = get_font_path()
        css_string = get_base_css(font_path)

        html_parts: list[str] = []

        title = (meta or {}).get("title") or "جزوه درسی"
        root = (structure or {}).get("root_object", {}) or {}
        summary = root.get("summary") or (meta or {}).get("description") or ""

        cover_html = f"""
        <div class=\"cover-page\">
            <h1>{title}</h1>
            <div style=\"margin-top: 2cm; font-size: 14pt;\">{summary}</div>
            <div class=\"footer-note\">ساخته شده توسط Amooz-AI</div>
        </div>
        """
        html_parts.append(cover_html)

        outline = (structure or {}).get("outline", []) or []
        toc_html = ["<div class='page-break'><h2>📚 فهرست مطالب</h2>"]

        for sec_idx, section in enumerate(outline, 1):
            stitle = clean_title_latex(section.get("title", f"فصل {sec_idx}"))
            toc_html.append(
                f"<div class='toc-item'><b>فصل {sec_idx}:</b> <a href='#sec-{sec_idx}' style='text-decoration:none; color:black;'>{stitle}</a></div>"
            )
            for unit in section.get("units", []) or []:
                utitle = clean_title_latex(unit.get("title", "زیرفصل"))
                toc_html.append(f"<div class='toc-subitem'>• {utitle}</div>")

        toc_html.append("</div>")
        html_parts.append("".join(toc_html))

        for sec_idx, section in enumerate(outline, 1):
            stitle = clean_title_latex(section.get("title", f"فصل {sec_idx}"))
            section_html = [f"<div class='page-break' id='sec-{sec_idx}'>"]
            section_html.append(f"<h2>فصل {sec_idx}: {stitle}</h2>")

            for unit in section.get("units", []) or []:
                utitle = clean_title_latex(unit.get("title", "زیرفصل"))
                section_html.append(f"<h3>📝 {utitle}</h3>")

                raw_content = (
                    unit.get("content_markdown")
                    or unit.get("teaching_markdown")
                    or unit.get("content")
                    or unit.get("source_markdown")
                    or ""
                )

                content_html = process_content_to_html(raw_content)
                section_html.append(f"<div>{content_html}</div>")

                for img in unit.get("images", []) or []:
                    img_path_raw = img if isinstance(img, str) else (img.get("path") or img.get("url"))
                    if not img_path_raw:
                        continue
                    img_clean = str(img_path_raw).strip()
                    section_html.append(f"<img src='{img_clean}' />")

            section_html.append("</div>")
            html_parts.append("".join(section_html))

        full_html = f"""
        <!DOCTYPE html>
        <html lang=\"fa\" dir=\"rtl\">
        <head>
            <meta charset=\"UTF-8\">
        </head>
        <body>
            {''.join(html_parts)}
        </body>
        </html>
        """

        font_config = FontConfiguration()
        pdf = HTML(string=full_html, base_url=base_url).write_pdf(
            font_config=font_config,
            stylesheets=[CSS(string=css_string, font_config=font_config)],
        )
        return pdf
    except Exception as e:
        logger.exception("Error generating PDF with WeasyPrint: %s", e)
        return None
