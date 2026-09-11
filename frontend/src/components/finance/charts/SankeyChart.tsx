import { useMemo } from "react";
import { sankey, sankeyLinkHorizontal, type SankeyNode, type SankeyLink } from "d3-sankey";
import type { CashflowSankey } from "@/lib/api/types";
import { BUCKET_COLORS, BUCKET_COLOR_FALLBACK } from "@/lib/api/theme";
import { formatCurrency } from "@/lib/format";

const INCOME_KEY = "__income__";
const CHART_WIDTH = 640;
const LABEL_FONT_SIZE = 12;
const LABEL_GAP = 8;
const ESTIMATED_CHAR_WIDTH = 7;

type NodeDatum = { name: string; color: string; key: string; expandable: boolean };
type LinkDatum = { color: string };
type Node = SankeyNode<NodeDatum, LinkDatum>;
type Link = SankeyLink<NodeDatum, LinkDatum>;

function displayNameForNode(name: string) {
  // Keep the stable HEALTH bucket key while giving users a descriptive label.
  return name === "HEALTH" ? "Medical and pharmacy" : name;
}

function labelForNode(
  name: string,
  amount: number,
  labelX: number,
  textAnchor: "start" | "end",
) {
  const displayName = displayNameForNode(name);
  const amountLabel = ` ${formatCurrency(amount, { compact: true })}`;
  const availableWidth = textAnchor === "start" ? CHART_WIDTH - labelX : labelX;
  const maxCharacters = Math.floor(availableWidth / ESTIMATED_CHAR_WIDTH);
  const fullLabelWidth = (displayName + amountLabel).length * ESTIMATED_CHAR_WIDTH;

  if (fullLabelWidth <= availableWidth || maxCharacters <= amountLabel.length + 2) {
    return { fullName: displayName, displayName, amountLabel, truncated: false };
  }

  const nameCharacters = Math.max(1, maxCharacters - amountLabel.length - 1);
  return {
    fullName: displayName,
    displayName: `${displayName.slice(0, Math.max(1, nameCharacters - 1))}…`,
    amountLabel,
    truncated: true,
  };
}

function hexToRgba(hex: string, alpha: number) {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

function buildGraph(data: CashflowSankey, expanded: string | null) {
  const nodes: NodeDatum[] = [];
  const links: Array<{ source: number; target: number; value: number; color: string }> = [];
  const push = (n: NodeDatum) => nodes.push(n) - 1;

  // The allocation hub is useful only when the server reports an exceptional
  // source of funding. In the ordinary case, linking Income directly to the
  // spending/savings destinations keeps the chart focused on the common story.
  const hasExceptionStage = data.deficit > 0 || data.netRefundCredits > 0;
  const incomeIdx = data.income > 0
    ? push({ name: "Income", color: "#10b981", key: "__income_node__", expandable: false })
    : null;
  const availableIdx = hasExceptionStage
    ? push({ name: "Available cash", color: "#34d399", key: "__available__", expandable: false })
    : null;

  let deficitIdx: number | null = null;
  if (data.deficit > 0 && availableIdx !== null) {
    deficitIdx = push({ name: "Deficit funding", color: "#dc2626", key: "__deficit__", expandable: false });
    links.push({ source: deficitIdx, target: availableIdx, value: data.deficit, color: "rgba(220,38,38,0.35)" });
  }

  if (data.netRefundCredits > 0 && availableIdx !== null) {
    const refundIdx = push({ name: "Net refund credits", color: "#0ea5e9", key: "__refund_credits__", expandable: false });
    links.push({ source: refundIdx, target: availableIdx, value: data.netRefundCredits, color: "rgba(14,165,233,0.35)" });
  }
  if (incomeIdx !== null) {
    const target = hasExceptionStage ? availableIdx : incomeIdx;
    // In the exception case income feeds the allocation stage. In the normal
    // case this is intentionally no self-link; destinations are linked below.
    if (target !== null && target !== incomeIdx) {
      links.push({ source: incomeIdx, target, value: data.income, color: "rgba(16,185,129,0.35)" });
    }
  }

  if (expanded === INCOME_KEY && incomeIdx !== null) {
    for (const src of data.incomeSources) {
      if (src.amount <= 0) continue;
      const i = push({ name: src.category, color: "#6ee7b7", key: `income:${src.category}`, expandable: false });
      links.push({ source: i, target: incomeIdx, value: src.amount, color: "rgba(16,185,129,0.35)" });
    }
  }

  const allocationIdx = hasExceptionStage ? availableIdx : incomeIdx;
  const bucketIdx = new Map<string, number>();
  for (const bucket of data.buckets) {
    if (allocationIdx === null || bucket.amount <= 0) continue;
    const color = BUCKET_COLORS[bucket.bucket] ?? BUCKET_COLOR_FALLBACK;
    const i = push({ name: bucket.bucket, color, key: `bucket:${bucket.bucket}`, expandable: bucket.categories.length > 0 });
    bucketIdx.set(bucket.bucket, i);
  }

  for (const bucket of data.buckets) {
    const target = bucketIdx.get(bucket.bucket);
    if (target === undefined) continue;
    if (allocationIdx !== null && bucket.amount > 0) {
      links.push({ source: allocationIdx, target, value: bucket.amount, color: "rgba(16,185,129,0.35)" });
    }
  }

  if (expanded && expanded !== INCOME_KEY) {
    const bucket = data.buckets.find((b) => b.bucket === expanded);
    const source = bucket ? bucketIdx.get(bucket.bucket) : undefined;
    if (bucket && source !== undefined) {
      const color = BUCKET_COLORS[bucket.bucket] ?? BUCKET_COLOR_FALLBACK;
      for (const cat of bucket.categories) {
        if (cat.amount <= 0) continue;
        const i = push({ name: cat.category, color, key: `cat:${cat.category}`, expandable: false });
        links.push({ source, target: i, value: cat.amount, color: hexToRgba(color, 0.35) });
      }
    }
  }

  if (data.savings > 0 && allocationIdx !== null) {
    const i = push({ name: "Savings", color: "#0ea5e9", key: "__savings__", expandable: false });
    links.push({ source: allocationIdx, target: i, value: data.savings, color: "rgba(14,165,233,0.35)" });
  }

  const columns = [
    expanded === INCOME_KEY
      ? data.incomeSources.filter((source) => source.amount > 0).length + (data.deficit > 0 ? 1 : 0) + (data.netRefundCredits > 0 ? 1 : 0)
      : (incomeIdx !== null ? 1 : 0) + (data.deficit > 0 ? 1 : 0) + (data.netRefundCredits > 0 ? 1 : 0),
    (incomeIdx !== null ? 1 : 0) + (availableIdx !== null ? 1 : 0),
    bucketIdx.size + (data.savings > 0 && allocationIdx !== null ? 1 : 0),
    expanded && expanded !== INCOME_KEY ? (data.buckets.find((b) => b.bucket === expanded)?.categories.length ?? 0) : 0,
  ];
  const height = Math.min(760, Math.max(320, 42 * Math.max(...columns) + 60));

  return { nodes, links, height };
}

export default function SankeyChart({
  data,
  expanded,
  onToggle,
}: {
  data: CashflowSankey;
  expanded: string | null;
  onToggle: (key: string) => void;
}) {
  const { height, laidOutNodes, laidOutLinks } = useMemo(() => {
    if (!data.sankeySupported) return { height: 0, laidOutNodes: [], laidOutLinks: [] };
    const graph = buildGraph(data, expanded);
    if (!graph.nodes.length || !graph.links.length) {
      return { height: graph.height, laidOutNodes: [], laidOutLinks: [] };
    }
    const generator = sankey<NodeDatum, LinkDatum>()
      .nodeWidth(14)
      .nodePadding(18)
      .extent([
        [1, 8],
        [CHART_WIDTH - 1, graph.height - 8],
      ]);
    const { nodes: laidOutNodes, links: laidOutLinks } = generator({
      nodes: graph.nodes.map((d) => ({ ...d })),
      links: graph.links.map((d) => ({ ...d })),
    });
    return { height: graph.height, laidOutNodes, laidOutLinks };
  }, [data, expanded]);

  if (!data.sankeySupported) {
    return (
      <p className="grid h-40 place-items-center text-center text-sm text-muted-foreground">
        {data.visualizationQualification ?? "Use the signed spending breakdown for this period; this flow chart cannot faithfully show refund credits."}
      </p>
    );
  }

  if (!laidOutNodes.length || !laidOutLinks.length) {
    return (
      <div className="grid h-40 place-items-center text-sm text-muted-foreground">
        No income or spending in this period.
      </div>
    );
  }

  const linkPath = sankeyLinkHorizontal<NodeDatum, LinkDatum>();

  return (
    <div>
      {data.netRefundCredits > 0 ? (
        <p className="mb-3 text-xs text-muted-foreground">
          <span className="font-medium text-sky-700">Net refund credits</span>: refunds remaining after offsetting spending in the same category. Not income.
        </p>
      ) : null}
      <svg viewBox={`0 0 ${CHART_WIDTH} ${height}`} width="100%" height={height} role="img" aria-label="Cashflow Sankey diagram">
      <g>
        {laidOutLinks.map((link: Link, i: number) => (
          <path
            key={i}
            d={linkPath(link) ?? undefined}
            fill="none"
            stroke={link.color}
            strokeWidth={Math.max(1, link.width ?? 0)}
          >
            <title>
              {`${(link.source as Node).name} → ${(link.target as Node).name}: ${formatCurrency(link.value)}`}
            </title>
          </path>
        ))}
      </g>
      <g>
        {laidOutNodes.map((n: Node) => {
          const isLeftHalf = (n.x0 ?? 0) < CHART_WIDTH / 2;
          const labelX = isLeftHalf ? (n.x1 ?? 0) + LABEL_GAP : (n.x0 ?? 0) - LABEL_GAP;
          const isExpanded = n.key === `bucket:${expanded}` || (n.key === "__income_node__" && expanded === INCOME_KEY);
          const clickable = n.expandable || (n.key === "__income_node__" && data.incomeSources.length > 0);
          const toggleKey = n.key === "__income_node__" ? INCOME_KEY : n.key.replace(/^bucket:/, "");
          const label = labelForNode(n.name, n.value ?? 0, labelX, isLeftHalf ? "start" : "end");
          const accessibleLabel = `${label.fullName}: ${formatCurrency(n.value ?? 0)}`;

          return (
            <g
              key={n.key}
              data-sankey-key={n.key}
              role={clickable ? "button" : undefined}
              tabIndex={clickable ? 0 : undefined}
              aria-label={clickable ? accessibleLabel : undefined}
              onKeyDown={
                clickable
                  ? (event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onToggle(toggleKey);
                      }
                    }
                  : undefined
              }
            >
              <rect
                x={n.x0}
                y={n.y0}
                width={Math.max(1, (n.x1 ?? 0) - (n.x0 ?? 0))}
                height={Math.max(1, (n.y1 ?? 0) - (n.y0 ?? 0))}
                rx={2}
                fill={n.color}
                stroke={isExpanded ? "currentColor" : "none"}
                strokeWidth={isExpanded ? 1.5 : 0}
                className={clickable ? "cursor-pointer" : undefined}
                onClick={clickable ? () => onToggle(toggleKey) : undefined}
              >
                <title>{`${n.name}: ${formatCurrency(n.value ?? 0)}`}</title>
              </rect>
              <text
                x={labelX}
                y={((n.y0 ?? 0) + (n.y1 ?? 0)) / 2}
                textAnchor={isLeftHalf ? "start" : "end"}
                dominantBaseline="middle"
                fontSize={LABEL_FONT_SIZE}
                data-full-label={label.fullName}
                aria-label={label.fullName}
                className={"select-none " + (clickable ? "cursor-pointer fill-foreground font-medium" : "fill-foreground")}
                onClick={clickable ? () => onToggle(toggleKey) : undefined}
              >
                {label.truncated ? <title>{`${n.name}: ${formatCurrency(n.value ?? 0)}`}</title> : null}
                {label.displayName}
                <tspan className="fill-muted-foreground">{label.amountLabel}</tspan>
              </text>
            </g>
          );
        })}
      </g>
      </svg>
    </div>
  );
}
