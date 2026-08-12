import { NextResponse } from "next/server";
import { parseSyllabus } from "@/lib/syllabus-parser";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const text = typeof body.text === "string" ? body.text : "";

    if (!text.trim()) {
      return NextResponse.json({ error: "Syllabus text is required" }, { status: 400 });
    }

    const parsed = parseSyllabus(text);
    return NextResponse.json(parsed);
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }
}
