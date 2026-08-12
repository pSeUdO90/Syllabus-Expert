"use client";

import { useState } from "react";
import type { ParsedSyllabus } from "@/lib/syllabus-parser";

const SAMPLE_SYLLABUS = `Course Title: Introduction to Computer Science
Instructor: Dr. Jane Smith
Schedule: Mon/Wed 10:00 AM - 11:30 AM
Grading: Exams 50%, Homework 30%, Participation 20%

Week 1: Introduction and setup
Week 2: Variables and data types
Week 3: Control flow
Topic 4: Functions and modules`;

export default function HomePage() {
  const [text, setText] = useState(SAMPLE_SYLLABUS);
  const [result, setResult] = useState<ParsedSyllabus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleParse() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error ?? "Failed to parse syllabus");
      }
      setResult(data);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <h1>Syllabus Expert</h1>
      <p className="subtitle">
        Paste syllabus text to extract course details, schedule, grading, and topics.
      </p>

      <div className="grid">
        <section className="card">
          <label htmlFor="syllabus-text">Syllabus text</label>
          <textarea
            id="syllabus-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste your syllabus here..."
          />
          <button type="button" onClick={handleParse} disabled={loading || !text.trim()}>
            {loading ? "Parsing..." : "Parse syllabus"}
          </button>
          {error && <p className="error">{error}</p>}
        </section>

        <section className="card">
          <h2 style={{ marginTop: 0 }}>Structured output</h2>
          {!result ? (
            <p className="subtitle">Parsed fields will appear here.</p>
          ) : (
            <div>
              <div className="field">
                <strong>Course</strong>
                {result.courseName ?? "—"}
              </div>
              <div className="field">
                <strong>Instructor</strong>
                {result.instructor ?? "—"}
              </div>
              <div className="field">
                <strong>Schedule</strong>
                {result.schedule ?? "—"}
              </div>
              <div className="field">
                <strong>Grading</strong>
                {result.grading ?? "—"}
              </div>
              <div className="field">
                <strong>Topics</strong>
                {result.topics.length > 0 ? (
                  <ul>
                    {result.topics.map((topic) => (
                      <li key={topic}>{topic}</li>
                    ))}
                  </ul>
                ) : (
                  "—"
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
