# Syllabus-Expert

An agent that extracts multiple-choice questions from PDF exam papers and writes them as structured JSON or CSV.

## How it works

PDF MCQ extraction is a pipeline, not a single prompt. Exam papers mix two-column layouts, answer keys, headers, and scans. The agent therefore splits the job:

```
PDF
 └─ 1. Page text (and optional page images)
      └─ 2. Heuristic parser for standard numbered items
           └─ 3. Tool-using LLM agent for messy / scanned papers
                └─ 4. Validated MCQ list (JSON or CSV)
```

### 1. Read the PDF as pages

Digital PDFs already contain text. [PyMuPDF](https://pymupdf.readthedocs.io/) pulls reading-order text per page. Pages with almost no characters are treated as scans: the agent can render them to PNG and send them to a vision model.

### 2. Parse the common exam layout without an API

Most practice papers look like this:

```
1. The SI unit of force is
(a) Joule
(b) Newton
(c) Watt
(d) Pascal
Answer: b
```

A heuristic parser matches question numbers, option letters `(a)` / `A.`, inline `Answer:` lines, and a trailing **Answer Key**. This path is deterministic, free, and is the default when no API key is set.

### 3. Use an agent when layout is messy

When the regex pass finds nothing useful (or you pass `--mode agent`), a small tool-using loop drives an OpenAI-compatible chat model:

| Tool | Purpose |
| --- | --- |
| `get_page_count` | Know the document size |
| `read_pages` | Pull text for a page range |
| `read_page_image` | Render a scanned page as PNG |
| `record_mcqs` | Save structured questions |
| `list_recorded` | Avoid duplicates |
| `finish` | Stop when the paper is done |

The model is not asked to “dump the whole PDF in one shot”. It pages through the file and records MCQs as it goes, which stays within context limits and reduces invented options.

### 4. Validate and export

Each item must have a stem and at least two options. Incomplete drafts are dropped with a warning. Output is JSON (default) or CSV.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

Heuristic only (no network):

```bash
syllabus-expert extract path/to/paper.pdf -o questions.json --mode heuristic
```

With a separate answer-key PDF (maps `Q1. c` letters and explanations onto the questions):

```bash
syllabus-expert extract path/to/paper.pdf \
  --answers path/to/answer-key.pdf \
  -o questions.json --mode heuristic
```

CSV:

```bash
syllabus-expert extract path/to/paper.pdf -o questions.csv --mode heuristic
```

LLM agent (OpenAI-compatible):

```bash
export OPENAI_API_KEY=sk-...
# optional: OPENAI_BASE_URL, OPENAI_MODEL
syllabus-expert extract path/to/paper.pdf -o questions.json --mode agent
```

`auto` (default) runs the heuristic first, then escalates to the agent if results look thin **and** `OPENAI_API_KEY` is set.

Debug the parser on plain text:

```bash
syllabus-expert from-text extracted.txt -o questions.json
```

Run the local website (home, library, upload, review, and practice quiz). Papers are stored in SQLite. Upload a question PDF and optional answer-key PDF to run extract → map → save:

```bash
syllabus-expert review
# same as:
syllabus-expert serve
# or import an existing JSON bank first:
syllabus-expert review questions.json
```

Then open http://127.0.0.1:8765.

| Page | What it does |
| --- | --- |
| `/` | Dashboard with library stats |
| `/upload` | Question PDF + optional answer-key PDF |
| `/library` | List, open, or delete saved papers |
| `/review` | Edit stems, mark answers, show LaTeX solutions |
| `/practice` | Quiz mode with a score at the end |

The database defaults to `data/syllabus_expert.db`.

Math is converted to LaTeX on extract (`½MR²` → `$\frac{1}{2}MR^{2}$`) and rendered with KaTeX. Edit mode in Review shows the raw `$...$` source.

## Output shape

```json
{
  "source_path": "/abs/path/paper.pdf",
  "page_count": 2,
  "mcqs": [
    {
      "number": "1",
      "question": "The SI unit of force is",
      "options": [
        {"letter": "A", "text": "Joule"},
        {"letter": "B", "text": "Newton"},
        {"letter": "C", "text": "Watt"},
        {"letter": "D", "text": "Pascal"}
      ],
      "answer": "B",
      "explanation": null,
      "page": 1,
      "source": "heuristic"
    }
  ],
  "warnings": []
}
```

## Python API

```python
from syllabus_expert import extract_mcqs

paper = extract_mcqs("paper.pdf", mode="heuristic")
for mcq in paper.mcqs:
    print(mcq.number, mcq.question, mcq.answer)
```

## Tests

```bash
pytest
```

## Limits

- Two-column papers can shuffle reading order; use `--mode agent` or a vision model.
- Scanned PDFs need `--mode agent` and a vision-capable `OPENAI_MODEL`.
- The heuristic expects numbered stems (`1.`, `Q.1`) and lettered options. Free-form quizzes belong on the agent path.
