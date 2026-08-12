import { test } from "node:test";
import assert from "node:assert/strict";
import { parseSyllabus } from "../lib/syllabus-parser.ts";

test("parseSyllabus extracts common syllabus fields", () => {
  const text = `Course Title: Data Structures
Instructor: Prof. Alan Turing
Schedule: Tue/Thu 2:00 PM - 3:30 PM
Grading: Midterm 40%, Final 40%, Labs 20%
Week 1: Arrays and linked lists
Week 2: Trees and graphs`;

  const result = parseSyllabus(text);

  assert.equal(result.courseName, "Data Structures");
  assert.equal(result.instructor, "Prof. Alan Turing");
  assert.equal(result.schedule, "Tue/Thu 2:00 PM - 3:30 PM");
  assert.equal(result.grading, "Midterm 40%, Final 40%, Labs 20%");
  assert.equal(result.topics.length, 2);
});
