export default function RecommendationBadge({ recommendation }: { recommendation: string }) {
  const isApprove = recommendation === "APPROVE";
  const isDeny = recommendation.startsWith("DENY");
  const isPend = recommendation.startsWith("PEND");

  const color = isApprove
    ? "bg-signal-pass/15 text-signal-pass border-signal-pass/40"
    : isDeny
    ? "bg-signal-fail/15 text-signal-fail border-signal-fail/40"
    : isPend
    ? "bg-signal-warn/15 text-signal-warn border-signal-warn/40"
    : "bg-panelLine/30 text-muted border-panelLine";

  return (
    <span className={`font-mono-data text-xs px-3 py-1.5 rounded-full border ${color}`}>
      {recommendation}
    </span>
  );
}
