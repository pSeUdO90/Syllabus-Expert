# Syllabus Expert

Parse unstructured course syllabus text into structured fields (course name, instructor, schedule, grading, and topics).

## Development

```bash
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), paste syllabus text, and click **Parse syllabus**.

## Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start the development server on port 3000 |
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm test` | Run unit tests |

## Cloud Agent environment

Repository-managed environment configuration lives in `.cursor/environment.json`. The install step runs `npm ci`; the dev server starts automatically in a named terminal.
