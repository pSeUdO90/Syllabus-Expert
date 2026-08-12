from syllabus_expert.latexify import latexify_mcq, latexify_text
from syllabus_expert.models import MCQ, Option


def test_fractions_and_powers():
    assert latexify_text("½MR²") == r"$\frac{1}{2}MR^{2}$"
    assert latexify_text("I = ½MR²") == r"$I = \frac{1}{2}MR^{2}$"


def test_sqrt_and_ratio():
    assert latexify_text("√2 : 1") == r"$\sqrt{2} : 1$"
    assert latexify_text("1 : √2") == r"$1 : \sqrt{2}$"
    assert latexify_text("k = √(I/M)") == r"$k = \sqrt{I/M}$"


def test_subscripts_and_omega():
    result = latexify_text("I₁ω₁ = I₂ω₂")
    assert r"I_{1}" in result
    assert r"\omega_{1}" in result
    assert result.startswith("$") and result.endswith("$")


def test_named_moments():
    result = latexify_text("Idisc = ½MR² and Iring = MR²")
    assert r"I_{\mathrm{disc}}" in result
    assert r"I_{\mathrm{ring}}" in result
    assert r"\frac{1}{2}MR^{2}" in result


def test_ascii_sqrt_function():
    assert r"\sqrt{I/M}" in (latexify_text("k = sqrt(I/M)") or "")
    once = latexify_text("½MR²")
    assert latexify_text(once) == once
    assert latexify_text("The SI unit of force is") == "The SI unit of force is"


def test_scientific_notation_is_wrapped():
    result = latexify_text("2.304 × 10-26 N")
    assert result.startswith("$")
    assert r"\times" in result
    assert r"10^{-26}" in result
    assert "N" in result


def test_option_powers_and_sqrt():
    assert r"a^{2}" in (latexify_text("5kq/a2") or "")
    assert r"a^{2}" in (latexify_text("kq/a2") or "")
    result = latexify_text("(√5)kq/a2")
    assert r"\sqrt{5}" in result
    assert r"a^{2}" in result


def test_sqrt_not_split_across_dollars():
    result = latexify_text(r"$2\pi \sqrt{4\pi\varepsilon0ma3$ / Qq}")
    assert result.count("$") % 2 == 0
    assert r"\sqrt{" in result
    inner = result.split("$")[1]
    assert inner.count("{") == inner.count("}")
    assert r"\varepsilon_0" in result
    assert r"a^{3}" in result or "ma^{3}" in result


def test_coulomb_constant():
    result = latexify_text("where k = 1/4πε0):")
    assert r"\frac{1}{4\pi\varepsilon_0}" in result
    assert r"\varepsilon_0" in result
    result = latexify_text("1.6 × 10-19 C")
    assert r"\times" in result
    assert r"10^{-19}" in result
    mcq = MCQ(
        number="1",
        question="Ratio kdisc : kring is",
        options=[Option(letter="A", text="√2 : 1"), Option(letter="B", text="1 : 2")],
        explanation="k = √(I/M)",
    )
    latexify_mcq(mcq)
    assert r"k_{\mathrm{disc}}" in mcq.question
    assert r"\sqrt{2}" in mcq.options[0].text
    assert r"\sqrt{I/M}" in (mcq.explanation or "")
