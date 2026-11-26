import { Node, Edge, MarkerType } from '@xyflow/react';
import { GraphNodeItem, GraphEdgeItem } from '../types';

export interface GraphLayoutResult {
  nodes: Node[];
  edges: Edge[];
}

/**
 * Computes layered DAG positions for GraphNodeItems per DESIGN_SYSTEM.md Section 8.1:
 * - Material flow from left to right:
 *   Tier 3 (Raw materials) -> Tier 2 -> Tier 1 -> Tier 0 (OEM Manufacturer) -> Production Lines
 * - Nodes in each tier column are distributed vertically with balanced offsets.
 */
export function layoutGraphNodes(
  rawNodes: GraphNodeItem[],
  rawEdges: GraphEdgeItem[]
): GraphLayoutResult {
  // 1. Group nodes into tier columns
  const tierColumns: Record<string, GraphNodeItem[]> = {
    tier3: [],
    tier2: [],
    tier1: [],
    oem: [],
    lines: [],
    other: [],
  };

  for (const node of rawNodes) {
    if (node.type === 'line') {
      tierColumns.lines.push(node);
    } else if (node.tier === 0 || node.label.toLowerCase().includes('automotive corp')) {
      tierColumns.oem.push(node);
    } else if (node.tier === 1) {
      tierColumns.tier1.push(node);
    } else if (node.tier === 2) {
      tierColumns.tier2.push(node);
    } else if (node.tier === 3) {
      tierColumns.tier3.push(node);
    } else {
      tierColumns.other.push(node);
    }
  }

  // 2. Column horizontal coordinates (X)
  const columnX: Record<string, number> = {
    other: 40,
    tier3: 40,
    tier2: 360,
    tier1: 680,
    oem: 1000,
    lines: 1320,
  };

  // If there are 'other' (untiered) nodes and tier3 nodes, push 'other' slightly or stack
  const VERTICAL_SPACING = 140;
  const TOP_PADDING = 80;

  // Determine max column height for vertical centering
  const counts = Object.values(tierColumns).map((col) => col.length);
  const maxInColumn = Math.max(1, ...counts);
  const totalHeight = maxInColumn * VERTICAL_SPACING;

  const nodes: Node[] = [];

  // 3. Position nodes column by column
  for (const [colKey, colNodes] of Object.entries(tierColumns)) {
    if (colNodes.length === 0) continue;

    const x = columnX[colKey] ?? 100;
    const colHeight = colNodes.length * VERTICAL_SPACING;
    const verticalOffset = TOP_PADDING + (totalHeight - colHeight) / 2;

    colNodes.forEach((nodeItem, index) => {
      // If untiered 'other' is in same column as tier3, offset Y
      let y = verticalOffset + index * VERTICAL_SPACING;
      if (colKey === 'other' && tierColumns.tier3.length > 0) {
        y = TOP_PADDING + (tierColumns.tier3.length + index) * VERTICAL_SPACING;
      }

      const nodeType = nodeItem.type === 'line' ? 'lineNode' : 'supplierNode';

      nodes.push({
        id: nodeItem.id,
        type: nodeType,
        position: { x, y },
        data: {
          nodeItem,
          label: nodeItem.label,
          tier: nodeItem.tier,
          risk_score: nodeItem.risk_score,
          region: nodeItem.region,
          flags: nodeItem.flags,
        },
      });
    });
  }

  // 4. Map rawEdges to React Flow Edges with design system styling
  const edges: Edge[] = rawEdges.map((e) => {
    const isPending = e.status === 'pending';
    const edgeColor = isPending ? '#3B6AF0' : '#8A93A6';

    // Width scales with share_pct (1.5px to 4px) per DESIGN_SYSTEM.md Section 8.3
    const strokeWidth =
      e.share_pct !== null && e.share_pct !== undefined
        ? Math.max(1.5, Math.min(4, 1.5 + (e.share_pct / 100) * 2.5))
        : 2;

    return {
      id: e.id,
      source: e.source,
      target: e.target,
      type: 'smoothstep',
      animated: isPending,
      label: e.material,
      labelStyle: {
        fontSize: 11,
        fontWeight: 500,
        fill: '#5B6478',
      },
      labelBgStyle: {
        fill: '#FFFFFF',
        fillOpacity: 0.9,
        rx: 4,
        ry: 4,
      },
      labelBgPadding: [6, 3] as [number, number],
      style: {
        stroke: edgeColor,
        strokeWidth,
        strokeDasharray: isPending ? '5 5' : undefined,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edgeColor,
        width: 14,
        height: 14,
      },
      data: {
        edgeItem: e,
        material: e.material,
        share_pct: e.share_pct,
        lead_time_days: e.lead_time_days,
        status: e.status,
      },
    };
  });

  return { nodes, edges };
}
