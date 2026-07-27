import { ListingStatus } from "@/lib/api";

const STYLES: Record<ListingStatus, string> = {
  pending: "border-ink/40 text-faint",
  approved: "border-ink bg-ink text-paper",
  rejected: "border-signal text-signal",
  removed: "border-ink/30 text-faint line-through",
};

const LABELS: Record<ListingStatus, string> = {
  pending: "in review",
  approved: "live",
  rejected: "changes needed",
  removed: "removed",
};

export function StatusBadge({ status }: { status: ListingStatus }) {
  return (
    <span
      className={`shrink-0 border px-1.5 py-0.5 text-[10px] uppercase tracking-micro ${STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
