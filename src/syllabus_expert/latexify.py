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
INFIX_OPS = {"=", ":", "+", "-", "/", r"\times", r"\cdot", r"\pm"}
UNITS = {"N", "C", "J", "V", "W", "Pa", "m", "s", "g", "A", "K", "kg", "eV"}
SUPER_RUN = re.compile(r"([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+)")
SUB_RUN = re.compile(r"([₀₁₂₃₄₅₆₇₈₉₊₋]+)")


def latexify_text(text: str | None) -> str | None:
    """Turn PDF/Unicode math into $-delimited LaTeX. Idempotent."""
    if text is None:
        return None
    if not text.strip():
        return text
    if _has_unbalanced_math(text):
        text = text.replace("$", "")
    pieces: list[str] = []
    for kind, chunk in _split_math_segments(text):
        if kind == "math":
            pieces.append(f"${_replace_unicode_math(chunk)}$")
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


def _has_unbalanced_math(text: str) -> bool:
    for kind, chunk in _split_math_segments(text):
        if kind == "math" and chunk.count("{") != chunk.count("}"):
            return True
    return False


def _split_math_segments(text: str) -> list[tuple[str, str]]:
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
    return _wrap_math(_replace_unicode_math(text))


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
    text = _normalize_sqrts(text)
    text = re.sub(r"(?<![\\A-Za-z])sqrt\s*\(([^)]*)\)", r"\\sqrt{\1}", text)
    text = re.sub(r"\\varepsilon0(?![0-9])", r"\\varepsilon_0", text)
    text = re.sub(r"\\epsilon0(?![0-9])", r"\\varepsilon_0", text)
    text = re.sub(r"(\\varepsilon_0)([A-Za-z])", r"\1 \2", text)
    text = re.sub(r"(\\times\s*)10[-−](\d+)", r"\g<1>10^{-\2}", text)
    text = re.sub(r"(?<![.\d\\])10[-−](\d+)\b", r"10^{-\1}", text)
    text = re.sub(
        r"1\s*/\s*4\s*\\pi\s*\\varepsilon(?:_0|0)",
        r"\\frac{1}{4\\pi\\varepsilon_0}",
        text,
    )
    if _looks_like_formula(text):
        text = re.sub(r"(?<![0-9\\_])([A-Za-z])(\d)(?![0-9])", r"\1^{\2}", text)
    return text


def _entirely_formula(text: str) -> bool:
    if re.search(
        r"\b(?:the|and|for|with|from|that|this|when|which|where|since|because|ratio|unit|force|mass)\b",
        text,
        flags=re.I,
    ):
        return False
    return _looks_like_formula(text) and len(text) < 120


def _looks_like_formula(text: str) -> bool:
    if "\\" in text or "/" in text or "√" in text:
        return True
    compact = text.replace(" ", "")
    return bool(re.fullmatch(r"[\d().A-Za-z/^+_{}\\-]+", compact) and re.search(r"[A-Za-z]\d", compact))


def _normalize_sqrts(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith(r"\sqrt", i):
            j = i + 5
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j] == "{":
                close = _matching(text, j, "{", "}")
                inner = text[j + 1 : close]
                out.append(r"\sqrt{" + inner + "}")
                i = close + 1
                continue
            if j < len(text) and text[j] == "(":
                close = _matching(text, j, "(", ")")
                inner = text[j + 1 : close]
                out.append(r"\sqrt{" + inner + "}")
                i = close + 1
                continue
            if j < len(text) and text[j] == "[":
                close = _matching(text, j, "[", "]")
                inner = text[j + 1 : close]
                out.append(r"\sqrt{" + inner + "}")
                i = close + 1
                continue
            k = j
            while k < len(text) and (text[k].isalnum() or text[k] in r"\/^_{}"):
                k += 1
            out.append(r"\sqrt{" + text[j:k] + "}")
            i = k
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _matching(text: str, open_idx: int, opener: str, closer: str) -> int:
    depth = 0
    for k in range(open_idx, len(text)):
        if text[k] == opener:
            depth += 1
        elif text[k] == closer:
            depth -= 1
            if depth == 0:
                return k
    return len(text) - 1


def _tokenize(text: str) -> list[str]:
    """Split on whitespace but keep \\command{...} groups intact."""
    tokens: list[str] = []
    i = 0
    while i < len(text):
        if text[i].isspace():
            j = i
            while j < len(text) and text[j].isspace():
                j += 1
            tokens.append(text[i:j])
            i = j
            continue
        if text[i] == "\\":
            j = i + 1
            while j < len(text) and text[j].isalpha():
                j += 1
            while j < len(text) and text[j] == "{":
                j = _matching(text, j, "{", "}") + 1
            tokens.append(text[i:j])
            i = j
            continue
        j = i + 1
        while j < len(text) and not text[j].isspace() and text[j] != "\\":
            j += 1
        tokens.append(text[i:j])
        i = j
    return tokens


def _is_math_atom(token: str) -> bool:
    stripped = token.strip()
    if not stripped or stripped in INFIX_OPS:
        return False
    return "\\" in stripped or "^{" in stripped or "_{" in stripped


def _is_number(token: str) -> bool:
    return bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", token.strip()))


def _is_short_id(token: str) -> bool:
    stripped = token.strip()
    return bool(re.fullmatch(r"[A-Za-z]{1,3}", stripped)) and stripped not in {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "are",
        "was",
        "not",
    }


def _next_nonspace(tokens: list[str], index: int, step: int) -> int | None:
    j = index + step
    while 0 <= j < len(tokens) and tokens[j].isspace():
        j += step
    if 0 <= j < len(tokens):
        return j
    return None


def _wrap_math(text: str) -> str:
    stripped = text.strip()
    if stripped and "$" not in text and _entirely_formula(stripped):
        leading = re.match(r"^\s*", text).group(0)
        trailing = re.search(r"\s*$", text).group(0)
        return f"{leading}${stripped}${trailing}"

    tokens = _tokenize(text)
    if not tokens:
        return text
    flags = [_is_math_atom(token) for token in tokens]

    def promote() -> bool:
        changed = False
        for i, token in enumerate(tokens):
            stripped = token.strip()
            prev = _next_nonspace(tokens, i, -1)
            nxt = _next_nonspace(tokens, i, 1)
            if stripped in INFIX_OPS and prev is not None and nxt is not None:
                left = flags[prev] or _is_number(tokens[prev]) or _is_short_id(tokens[prev])
                right = flags[nxt] or _is_number(tokens[nxt]) or _is_short_id(tokens[nxt])
                seeded = flags[prev] or flags[nxt] or _is_number(tokens[prev]) or _is_number(tokens[nxt])
                if left and right and seeded:
                    for idx in (i, prev, nxt):
                        if not flags[idx]:
                            flags[idx] = True
                            changed = True
            elif stripped in UNITS and prev is not None and flags[prev] and not flags[i]:
                flags[i] = True
                changed = True
            elif _is_number(token) and not flags[i]:
                if (prev is not None and flags[prev]) or (nxt is not None and flags[nxt]):
                    flags[i] = True
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
        if core.count("{") > core.count("}"):
            core += "}" * (core.count("{") - core.count("}"))
        out.append(f"{leading}${core}${punct}{trailing}")
    return "".join(out)
