from __future__ import annotations

import re

from syllabus_expert.models import MCQ

UNICODE_TO_LATEX = {
    "½": r"\frac{1}{2}",
    "⅓": r"\frac{1}{3}",
    "⅔": r"\frac{2}{3}",
    "¼": r"\frac{1}{4}",
    "¾": r"\frac{3}{4}",
    "⅕": r"\frac{1}{5}",
    "⅖": r"\frac{2}{5}",
    "⅗": r"\frac{3}{5}",
    "⅘": r"\frac{4}{5}",
    "⅙": r"\frac{1}{6}",
    "⅚": r"\frac{5}{6}",
    "⅛": r"\frac{1}{8}",
    "⅜": r"\frac{3}{8}",
    "⅝": r"\frac{5}{8}",
    "⅞": r"\frac{7}{8}",
    "×": r"\times",
    "·": r"\cdot",
    "±": r"\pm",
    "∓": r"\mp",
    "≤": r"\le",
    "≥": r"\ge",
    "≠": r"\ne",
    "≈": r"\approx",
    "∞": r"\infty",
    "°": r"^{\circ}",
    "θ": r"\theta",
    "ω": r"\omega",
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "δ": r"\delta",
    "Δ": r"\Delta",
    "π": r"\pi",
    "μ": r"\mu",
    "σ": r"\sigma",
    "τ": r"\tau",
    "λ": r"\lambda",
    "φ": r"\phi",
    "Φ": r"\Phi",
    "ρ": r"\rho",
    "η": r"\eta",
    "ε": r"\varepsilon",
    "Ω": r"\Omega",
    "Σ": r"\Sigma",
    "→": r"\rightarrow",
    "←": r"\leftarrow",
    "↔": r"\leftrightarrow",
    "⇒": r"\Rightarrow",
    "≡": r"\equiv",
    "∝": r"\propto",
    "∑": r"\sum",
    "∫": r"\int",
    "√": r"\sqrt",
}

SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋", "0123456789+-")

IDENTIFIERS = (
    ("kdisc", r"k_{\mathrm{disc}}"),
    ("kring", r"k_{\mathrm{ring}}"),
    ("Idisc", r"I_{\mathrm{disc}}"),
    ("Iring", r"I_{\mathrm{ring}}"),
    ("Ktrans", r"K_{\mathrm{trans}}"),
    ("Xcm", r"X_{\mathrm{cm}}"),
    ("Ycm", r"Y_{\mathrm{cm}}"),
    ("Vcm", r"V_{\mathrm{cm}}"),
    ("I1", r"I_{1}"),
    ("I2", r"I_{2}"),
)

SQRT_GROUP = re.compile(r"\\sqrt\s*(?:\[([^\]]*)\]|\(([^)]*)\)|\{([^{}]*)\}|([A-Za-z0-9]+(?:/[A-Za-z0-9]+)?))")
SUPER_RUN = re.compile(r"([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+)")
SUB_RUN = re.compile(r"([₀₁₂₃₄₅₆₇₈₉₊₋]+)")
MATH_ATOM = re.compile(
    r"\\[a-zA-Z]+(?:\s*\{[^{}]*\})*|[A-Za-z][A-Za-z0-9]*(?:_\{[^{}]+\})?(?:\^\{[^{}]+\})?|\^\{[^{}]+\}|_\{[^{}]+\}"
)


def latexify_text(text: str | None) -> str | None:
    """Turn PDF/Unicode math into $-delimited LaTeX. Idempotent."""
    if text is None:
        return None
    if not text.strip():
        return text
    pieces: list[str] = []
    for kind, chunk in _split_math_segments(text):
        if kind == "math":
            pieces.append(f"${chunk}$")
        else:
            pieces.append(_convert_and_wrap(chunk))
    return "".join(pieces)


def latexify_mcq(mcq: MCQ) -> MCQ:
    mcq.question = latexify_text(mcq.question) or mcq.question
    if mcq.explanation:
        mcq.explanation = latexify_text(mcq.explanation)
    for option in mcq.options:
        option.text = latexify_text(option.text) or option.text
    return mcq


def _split_math_segments(text: str) -> list[tuple[str, str]]:
    """Split on $...$ / $$...$$ so existing LaTeX is left alone."""
    parts: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        if text.startswith("$$", i):
            end = text.find("$$", i + 2)
            if end == -1:
                parts.append(("text", text[i:]))
                break
            parts.append(("math", text[i + 2 : end]))
            i = end + 2
        elif text[i] == "$":
            end = text.find("$", i + 1)
            if end == -1:
                parts.append(("text", text[i:]))
                break
            parts.append(("math", text[i + 1 : end]))
            i = end + 1
        else:
            next_dollar = text.find("$", i)
            if next_dollar == -1:
                parts.append(("text", text[i:]))
                break
            parts.append(("text", text[i:next_dollar]))
            i = next_dollar
    return parts


def _convert_and_wrap(text: str) -> str:
    converted = _replace_unicode_math(text)
    return _wrap_math(converted)


def _replace_unicode_math(text: str) -> str:
    def super_sub(match: re.Match[str], kind: str) -> str:
        raw = match.group(1)
        table = SUPERSCRIPTS if kind == "super" else SUBSCRIPTS
        body = raw.translate(table)
        return f"^{{{body}}}" if kind == "super" else f"_{{{body}}}"

    text = SUPER_RUN.sub(lambda m: super_sub(m, "super"), text)
    text = SUB_RUN.sub(lambda m: super_sub(m, "sub"), text)
    for src, dst in IDENTIFIERS:
        text = re.sub(rf"\b{re.escape(src)}\b", lambda _match, repl=dst: repl, text)
    for src, dst in UNICODE_TO_LATEX.items():
        if src != "√":
            text = text.replace(src, dst)
    text = text.replace("√", r"\sqrt")
    text = SQRT_GROUP.sub(_normalize_sqrt, text)
    text = re.sub(r"(?<![\\A-Za-z])sqrt\s*\(([^)]*)\)", r"\\sqrt{\1}", text)
    text = re.sub(r"(\\times\s*)10[-−](\d+)", r"\1 10^{-\2}", text)
    text = re.sub(r"(?<![.\d])10[-−](\d+)\b", r"10^{-\1}", text)
    return text


def _normalize_sqrt(match: re.Match[str]) -> str:
    inner = next((group for group in match.groups() if group), "")
    return rf"\sqrt{{{inner}}}"


def _is_math_atom(token: str) -> bool:
    stripped = token.strip()
    if not stripped:
        return False
    if stripped in {"=", ":", "+", "-", "/", r"\times", r"\cdot", r"\pm"}:
        return False
    if "\\" in stripped or "^{" in stripped or "_{" in stripped:
        return True
    return bool(MATH_ATOM.fullmatch(stripped)) and (
        "^{" in stripped or "_{" in stripped or stripped.startswith("\\")
    )


def _is_number(token: str) -> bool:
    return bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", token.strip()))


def _is_short_id(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]{1,2}", token.strip()))


def _next_nonspace(tokens: list[str], index: int, step: int) -> int | None:
    j = index + step
    while 0 <= j < len(tokens) and tokens[j].isspace():
        j += step
    if 0 <= j < len(tokens):
        return j
    return None


def _wrap_math(text: str) -> str:
    tokens = re.findall(r"\s+|[^\s]+", text)
    if not tokens:
        return text
    flags = [_is_math_atom(token) for token in tokens]

    def promote() -> bool:
        changed = False
        for i, token in enumerate(tokens):
            stripped = token.strip()
            prev = _next_nonspace(tokens, i, -1)
            nxt = _next_nonspace(tokens, i, 1)
            if stripped not in {"=", ":", "+", "-", "/"} or prev is None or nxt is None:
                continue
            left = flags[prev] or _is_number(tokens[prev]) or _is_short_id(tokens[prev])
            right = flags[nxt] or _is_number(tokens[nxt]) or _is_short_id(tokens[nxt])
            seeded = flags[prev] or flags[nxt] or _is_number(tokens[prev]) or _is_number(tokens[nxt])
            if left and right and seeded:
                for idx in (i, prev, nxt):
                    if not flags[idx]:
                        flags[idx] = True
                        changed = True
        return changed

    for _ in range(len(tokens) + 2):
        if not promote():
            break

    out: list[str] = []
    i = 0
    while i < len(tokens):
        if not flags[i]:
            out.append(tokens[i])
            i += 1
            continue
        start = i
        i += 1
        while i < len(tokens) and (
            flags[i] or (tokens[i].isspace() and i + 1 < len(tokens) and flags[i + 1])
        ):
            i += 1
        raw = "".join(tokens[start:i])
        leading = re.match(r"^\s*", raw).group(0)
        trailing = re.search(r"\s*$", raw).group(0)
        end = len(raw) - len(trailing) if trailing else len(raw)
        core = raw[len(leading) : end]
        if not core:
            out.append(raw)
            continue
        punct = ""
        while core and core[-1] in ",.;:!?":
            punct = core[-1] + punct
            core = core[:-1]
        if not core:
            out.append(raw)
            continue
        out.append(f"{leading}${core}${punct}{trailing}")
    return "".join(out)
