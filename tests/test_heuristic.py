from syllabus_expert.heuristic import parse_mcqs
from syllabus_expert.pdf import PageText


def test_parses_parenthetical_and_dotted_options(sample_pages):
    mcqs, warnings = parse_mcqs(sample_pages)
    assert [mcq.number for mcq in mcqs] == ["1", "2", "3"]
    assert mcqs[0].question == "The SI unit of force is"
    assert [opt.letter for opt in mcqs[0].options] == ["A", "B", "C", "D"]
    assert mcqs[0].options[1].text == "Newton"
    assert mcqs[0].answer == "B"
    assert mcqs[1].options[2].text == "Velocity"
    assert mcqs[1].answer == "C"
    assert mcqs[2].answer == "A"
    assert not any("No numbered MCQs" in w for w in warnings)


def test_multiline_question_and_option():
    text = """
1. Which statement about an ideal gas is correct when
the temperature is doubled at constant volume?
(a) Pressure is halved
(b) Pressure is doubled
because PV = nRT
(c) Pressure is unchanged
(d) Pressure becomes zero
"""
    mcqs, _ = parse_mcqs([PageText(page=1, text=text, char_count=len(text))])
    assert len(mcqs) == 1
    assert "temperature is doubled" in mcqs[0].question
    assert mcqs[0].options[1].text == "Pressure is doubled because PV = nRT"


def test_q_prefix_and_answer_key_only():
    text = """
Q.1 Light year is a unit of
(A) time
(B) distance
(C) mass
(D) energy

Q2. The chemical formula of water is
(a) H2O
(b) CO2
(c) O2
(d) NaCl

ANSWERS
1. B  2. a
"""
    mcqs, _ = parse_mcqs([PageText(page=1, text=text, char_count=len(text))])
    assert len(mcqs) == 2
    assert mcqs[0].number == "1"
    assert mcqs[0].answer == "B"
    assert mcqs[1].number == "2"
    assert mcqs[1].answer == "A"


def test_skips_incomplete_item_without_options():
    text = """
1. This is just a heading without choices.

2. Real question?
(a) yes
(b) no
"""
    mcqs, warnings = parse_mcqs([PageText(page=1, text=text, char_count=len(text))])
    assert len(mcqs) == 1
    assert mcqs[0].number == "2"
    assert any("Skipped incomplete" in w for w in warnings)


def test_question_spans_pages():
    pages = [
        PageText(page=1, text="1. What is 2+2?\n(a) 3", char_count=20),
        PageText(page=2, text="(b) 4\n(c) 5\n(d) 6\nAnswer: b", char_count=30),
    ]
    mcqs, _ = parse_mcqs(pages)
    assert len(mcqs) == 1
    assert mcqs[0].page == 1
    assert [opt.text for opt in mcqs[0].options] == ["3", "4", "5", "6"]
    assert mcqs[0].answer == "B"


def test_neet_q_prefix_and_letter_on_own_line():
    text = """
Q1.
A uniform disc and a uniform ring have the same mass and radius.
The ratio of their radii of gyration is:
A.
1 : 2
B.
√2 : 1
C.
1 : √2
D.
2 : 1
Q2.
Assertion (A): Angular momentum remains constant.
Reason (R): Net torque about the center is zero.
A.
Both (A) and (R) are true and (R) is the correct explanation of (A).
B.
Both (A) and (R) are true but (R) is NOT the correct explanation of (A).
C.
(A) is true but (R) is false.
D.
(A) is false but (R) is true.
Q3.
Consider the following statements:
1. The velocity of the point of contact with the ground is zero.
2. The ratio of rotational KE to translational KE is 2:5.
How many of the above statements are correct?
A.
Only one
B.
Only two
C.
Only three
D.
All four
"""
    mcqs, warnings = parse_mcqs([PageText(page=1, text=text, char_count=len(text))])
    assert [mcq.number for mcq in mcqs] == ["1", "2", "3"]
    assert mcqs[0].options[1].text == "√2 : 1"
    assert mcqs[1].options[2].text == "(A) is true but (R) is false."
    assert "point of contact" in mcqs[2].question
    assert mcqs[2].options[0].text == "Only one"
    assert not any("Skipped incomplete" in w for w in warnings)


def test_parse_and_apply_answer_key():
    from syllabus_expert.heuristic import apply_answer_key, parse_answer_key

    key_text = """
Practice Paper of NEET (UG) - 06 - Answer Key
Q1.
c
Since Idisc = ½MR², kdisc = R/√2.
Q2.
a
Torque is zero so L is constant.
Q3.
b
"""
    mapping, warnings = parse_answer_key(
        [PageText(page=1, text=key_text, char_count=len(key_text))]
    )
    assert mapping["1"][0] == "C"
    assert "kdisc" in (mapping["1"][1] or "")
    assert mapping["2"] == ("A", "Torque is zero so L is constant.")
    assert mapping["3"][0] == "B"
    assert not warnings

    mcqs, _ = parse_mcqs(
        [
            PageText(
                page=1,
                text="Q1.\nStem one?\nA.\none\nB.\ntwo\nC.\nthree\nD.\nfour\n"
                "Q2.\nStem two?\nA.\nx\nB.\ny\nC.\nz\nD.\nw\n",
                char_count=80,
            )
        ]
    )
    apply_warnings = apply_answer_key(mcqs, mapping)
    assert mcqs[0].answer == "C"
    assert "kdisc" in (mcqs[0].explanation or "")
    assert mcqs[1].answer == "A"
    assert any("1 item" in w for w in apply_warnings)


def test_empty_text_warns():
    mcqs, warnings = parse_mcqs([PageText(page=1, text="Syllabus only.", char_count=14)])
    assert mcqs == []
    assert any("No numbered MCQs" in w for w in warnings)
