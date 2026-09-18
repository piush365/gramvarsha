import { NextResponse } from "next/server";

type FeedbackEntry = { gpId: string; accurate: boolean; at: string };

// In-memory only — resets on cold start. Good enough for a hackathon demo;
// swap for a real datastore (e.g. Supabase) before this needs to persist.
const feedbackLog: FeedbackEntry[] = [];

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  const gpId = body?.gpId;
  const accurate = body?.accurate;

  if (typeof gpId !== "string" || typeof accurate !== "boolean") {
    return NextResponse.json({ error: "Invalid payload" }, { status: 400 });
  }

  feedbackLog.push({ gpId, accurate, at: new Date().toISOString() });
  return NextResponse.json({ ok: true, count: feedbackLog.length });
}

export async function GET() {
  return NextResponse.json({ entries: feedbackLog });
}
