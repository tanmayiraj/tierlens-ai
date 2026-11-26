import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { GraphNodeItem } from '../../types';
import { Factory, Activity } from 'lucide-react';

export interface LineNodeData {
  nodeItem: GraphNodeItem;
  label: string;
  tier: number | null;
  risk_score: number;
  region: string | null;
  flags: string[];
}

/**
 * Custom React Flow Node for Production Lines per DESIGN_SYSTEM.md Section 8.2:
 * - Represents final automotive manufacturing lines (e.g. Sedan X)
 * - Industrial slate/amber outline with line icon
 */
export const LineNode = memo(({ data, selected }: NodeProps) => {
  const nodeData = data as unknown as LineNodeData;

  return (
    <div
      className={`relative w-60 bg-surface rounded-lg p-3 border-2 border-slate-700 shadow-sm transition-all duration-150 select-none ${
        selected ? 'ring-2 ring-brand-600 shadow-md -translate-y-0.5' : 'hover:shadow-md'
      }`}
    >
      {/* Target handle (parts incoming from Tier 1 / OEM) */}
      <Handle
        type="target"
        position={Position.Left}
        className="w-2.5 h-2.5 bg-slate-700 border-2 border-white rounded-full -ml-1.5"
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-1.5">
        <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
          <Factory className="w-3 h-3" />
          <span>Production Line</span>
        </span>
        <span className="flex items-center gap-1 text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">
          <Activity className="w-2.5 h-2.5" /> Active
        </span>
      </div>

      {/* Center: Line Name */}
      <div className="text-xs font-bold text-appText leading-tight line-clamp-1" title={nodeData.label}>
        {nodeData.label}
      </div>
      <p className="text-[10px] text-appText-muted mt-0.5">
        {nodeData.region || 'Assembly Facility'}
      </p>
    </div>
  );
});

LineNode.displayName = 'LineNode';
export default LineNode;
