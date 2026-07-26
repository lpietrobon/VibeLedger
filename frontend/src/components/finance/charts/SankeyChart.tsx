import { useMemo } from "react";
import { sankey, sankeyLinkHorizontal, type SankeyNode, type SankeyLink } from "d3-sankey";
import type { CashflowSankey } from "@/lib/api/types";
import { BUCKET_COLORS, BUCKET_COLOR_FALLBACK } from "@/lib/api/theme";
import { formatCurrency } from "@/lib/format";

const INCOME_KEY = "__income__";
const CHART_WIDTH = 640;

type NodeDatum = { name: string; color: string; key: string; expandable: boolean };
type LinkDatum = { color: string };
type Node = SankeyNode<NodeDatum, LinkDatum>;
type Link = SankeyLink<NodeDatum, LinkDatum>;

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

  const incomeIdx = push({ name: "Income", color: "#10b981", key: "__income_node__", expandable: false });

  let deficitIdx: number | null = null;
  if (data.deficit > 0) {
    deficitIdx = push({ name: "Deficit funding", color: "#dc2626", key: "__deficit__", expandable: false });
  }

  if (expanded === INCOME_KEY) {
    for (const src of data.incomeSources) {
      const i = push({ name: src.category, color: "#6ee7b7", key: `income:${src.category}`, expandable: false });
      links.push({ source: i, target: incomeIdx, value: src.amount, color: "rgba(16,185,129,0.35)" });
    }
  }

  const bucketIdx = new Map<string, number>();
  for (const bucket of data.buckets) {
    const color = BUCKET_COLORS[bucket.bucket] ?? BUCKET_COLOR_FALLBACK;
    const i = push({ name: bucket.bucket, color, key: `bucket:${bucket.bucket}`, expandable: bucket.categories.length > 0 });
    bucketIdx.set(bucket.bucket, i);
  }

  const availableForSpend = Math.min(data.income, data.totalSpend);
  for (const bucket of data.buckets) {
    const target = bucketIdx.get(bucket.bucket);
    if (target === undefined) continue;
    const incomeShare = data.totalSpend > 0 ? (bucket.amount * availableForSpend) / data.totalSpend : 0;
    const deficitShare = bucket.amount - incomeShare;
    if (incomeShare > 0) {
      links.push({ source: incomeIdx, target, value: incomeShare, color: "rgba(16,185,129,0.35)" });
    }
    if (deficitShare > 0 && deficitIdx !== null) {
      links.push({ source: deficitIdx, target, value: deficitShare, color: "rgba(220,38,38,0.35)" });
    }
  }

  if (expanded && expanded !== INCOME_KEY) {
    const bucket = data.buckets.find((b) => b.bucket === expanded);
    const source = bucket ? bucketIdx.get(bucket.bucket) : undefined;
    if (bucket && source !== undefined) {
      const color = BUCKET_COLORS[bucket.bucket] ?? BUCKET_COLOR_FALLBACK;
      for (const cat of bucket.categories) {
        const i = push({ name: cat.category, color, key: `cat:${cat.category}`, expandable: false });
        links.push({ source, target: i, value: cat.amount, color: hexToRgba(color, 0.35) });
      }
    }
  }

  if (data.savings > 0) {
    const i = push({ name: "Savings", color: "#0ea5e9", key: "__savings__", expandable: false });
    links.push({ source: incomeIdx, target: i, value: data.savings, color: "rgba(14,165,233,0.35)" });
  }

  const columns = [
    (expanded === INCOME_KEY ? data.incomeSources.length : 0) + (data.deficit > 0 ? 1 : 0),
    1,
    data.buckets.length + (data.savings > 0 ? 1 : 0),
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
    const graph = buildGraph(data, expanded);
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

  if (!laidOutNodes.length || !laidOutLinks.length) {
    return (
      <div className="grid h-40 place-items-center text-sm text-muted-foreground">
        No income or spending in this period.
      </div>
    );
  }

  const linkPath = sankeyLinkHorizontal<NodeDatum, LinkDatum>();

  return (
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
          const labelX = isLeftHalf ? (n.x1 ?? 0) + 6 : (n.x0 ?? 0) - 6;
          const isExpanded = n.key === `bucket:${expanded}` || (n.key === "__income_node__" && expanded === INCOME_KEY);
          const clickable = n.expandable || (n.key === "__income_node__" && data.incomeSources.length > 0);
          const toggleKey = n.key === "__income_node__" ? INCOME_KEY : n.key.replace(/^bucket:/, "");

          return (
            <g key={n.key}>
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
                className={"select-none text-[10px] " + (clickable ? "cursor-pointer fill-foreground font-medium" : "fill-foreground")}
                onClick={clickable ? () => onToggle(toggleKey) : undefined}
              >
                {n.name}
                <tspan className="fill-muted-foreground"> {formatCurrency(n.value ?? 0, { compact: true })}</tspan>
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}
