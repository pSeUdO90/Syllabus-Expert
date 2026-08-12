export interface ParsedSyllabus {
  courseName: string | null;
  instructor: string | null;
  schedule: string | null;
  grading: string | null;
  topics: string[];
}

const COURSE_PATTERNS = [
  /(?:course\s*(?:title|name)?\s*[:]\s*)(.+)/i,
  /^([A-Z]{2,4}\s*\d{3,4}[A-Z]?(?:\s*[-:]\s*.+)?)/m,
];

const INSTRUCTOR_PATTERNS = [
  /(?:instructor|professor|faculty)\s*[:]\s*(.+)/i,
];

const SCHEDULE_PATTERNS = [
  /(?:schedule|meeting\s*times?)\s*[:]\s*(.+)/i,
  /((?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\s+\d{1,2}:\d{2}\s*(?:am|pm)?(?:\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm)?)?)/i,
];

const GRADING_PATTERNS = [
  /(?:grading|grade\s*distribution)\s*[:]\s*(.+)/i,
];

function firstMatch(text: string, patterns: RegExp[]): string | null {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match?.[1]) {
      return match[1].trim();
    }
  }
  return null;
}

export function parseSyllabus(text: string): ParsedSyllabus {
  const normalized = text.replace(/\r\n/g, "\n").trim();

  const topicLines = normalized
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => /^(?:week\s+\d+|topic\s+\d+|\d+\.)[:\s]+/i.test(line))
    .slice(0, 10);

  return {
    courseName: firstMatch(normalized, COURSE_PATTERNS),
    instructor: firstMatch(normalized, INSTRUCTOR_PATTERNS),
    schedule: firstMatch(normalized, SCHEDULE_PATTERNS),
    grading: firstMatch(normalized, GRADING_PATTERNS),
    topics: topicLines,
  };
}
