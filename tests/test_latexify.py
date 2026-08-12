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


def test_scientific_notation():
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
