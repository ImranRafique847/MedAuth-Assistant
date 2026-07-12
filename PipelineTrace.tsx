"use client";

const STAGES = [
  { key: "eligibility_gate", label: "Eligibility" },
  { key: "compliance_gate", label: "Compliance" },
  { key: "clinical_gate", label: "Clinical" },
  { key: "coverage_gate", label: "Coverage" },
];

function statusColor(status: string | undefined) {
  if (!status) return "#22304A";
  if (status === "PASS") return "#3FB68B";
  if (status === "FAIL") return "#D65A4A";
  if (status === "SKIPPED") return "#8C97AD";
  return "#E8A33D";
}

export default function PipelineTrace({
  gates,
  running,
}: {
  gates?: Record<string, string>;
  running?: boolean;
}) {
  const width = 720;
  const height = 90;
  const stepX = width / (STAGES.length + 1);
  const midY = height / 2;

  // Build a jagged EKG-like path between stages
  const points: [number, number][] = [[0, midY]];
  STAGES.forEach((_, i) => {
    const x = stepX * (i + 1);
    points.push([x - 14, midY]);
    points.push([x - 6, midY - 22]);
    points.push([x, midY + 16]);
    points.push([x + 6, midY]);
  });
  points.push([width, midY]);

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p[0]} ${p[1]}`)
    .join(" ");

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-24 pulse-trace"
        preserveAspectRatio="xMinYMid meet"
      >
        <path
          d={pathD}
          fill="none"
          stroke="#22304A"
          strokeWidth={1.5}
        />
        <path
          d={pathD}
          fill="none"
          stroke="#5B8DEF"
          strokeWidth={1.5}
          opacity={running ? 1 : 0}
        />
        {STAGES.map((stage, i) => {
          const x = stepX * (i + 1);
          const status = gates?.[stage.key];
          const color = statusColor(status);
          return (
            <g key={stage.key}>
              <circle cx={x} cy={midY} r={5} fill={color} />
              <circle
                cx={x}
                cy={midY}
                r={9}
                fill="none"
                stroke={color}
                strokeWidth={1}
                opacity={0.4}
              />
              <text
                x={x}
                y={midY + 32}
                textAnchor="middle"
                fontSize="11"
                fontFamily="IBM Plex Mono, monospace"
                fill="#8C97AD"
              >
                {stage.label}
              </text>
              <text
                x={x}
                y={midY - 20}
                textAnchor="middle"
                fontSize="9"
                fontFamily="IBM Plex Mono, monospace"
                fill={color}
                fontWeight={500}
              >
                {status || "—"}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
