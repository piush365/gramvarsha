import type { Source } from "@/lib/api";

const time = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Says exactly where the numbers on screen come from and how fresh they are. */
export default function StatusBanner({
  source,
  generatedAt,
  stale,
  staleSince,
}: {
  source: Source;
  generatedAt: string;
  stale: boolean;
  staleSince: string | null;
}) {
  if (source === "snapshot")
    return (
      <div className="border-b border-amber/40 bg-amber-soft px-4 py-1.5 text-xs text-ink sm:px-6">
        Showing the offline copy from {time(generatedAt)}. The live server is not reachable right now; this copy was
        made by the same pipeline.
      </div>
    );
  if (stale)
    return (
      <div className="border-b border-amber/40 bg-amber-soft px-4 py-1.5 text-xs text-ink sm:px-6">
        Forecast source unreachable. Showing the last good forecast, stale since {time(staleSince ?? generatedAt)}.
      </div>
    );
  return null;
}
