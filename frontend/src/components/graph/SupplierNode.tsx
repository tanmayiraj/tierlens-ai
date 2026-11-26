import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { GraphNodeItem } from '../../types';
import { TierBadge } from '../common/TierBadge';
import { RiskBadge } from '../common/RiskBadge';
import { Building2, AlertTriangle, ShieldCheck } from 'lucide-react';

export interface SupplierNodeData {
  nodeItem: GraphNodeItem;
  label: string;
  tier: number | null;
  risk_score: number;
  region: string | null;
  flags: string[];
}

/**
 * Custom React Flow Node for Suppliers per DESIGN_SYSTEM.md Section 8.2:
 * - Outline colour: Tier (Tier 1: Blue, Tier 2: Teal, Tier 3: Violet, OEM: Dark)
 * - Fill: Soft risk background or clean surface
 * - Handles: Left (target/incoming flow) and Right (source/outgoing flow)
 */
export const SupplierNode = memo(({ data, selected }: NodeProps) => {
  const nodeData = data as unknown as SupplierNodeData;
  const isOEM = nodeData.tier === 0 || nodeData.label.toLowerCase().includes('automotive corp');

  // Tier outline colors per Section 3.4
  const getTierBorderColor = () => {
    if (isOEM) return 'border-tier-0 ring-1 ring-tier-0/30';
    if (nodeData.tier === 1) return 'border-tier-1 ring-1 ring-tier-1/30';
    if (nodeData.tier === 2) return 'border-tier-2 ring-1 ring-tier-2/30';
    if (nodeData.tier === 3) return 'border-tier-3 ring-1 ring-tier-3/30';
    return 'border-tier-4';
  };

  return (
    <div
      className={`relative w-64 bg-surface rounded-lg p-3.5 border-2 shadow-sm transition-all duration-150 select-none ${getTierBorderColor()} ${
        selected ? 'ring-2 ring-brand-600 shadow-md -translate-y-0.5' : 'hover:shadow-md'
      }`}
    >
      {/* Target handle (material incoming from upstream) */}
      {!isOEM && (
        <Handle
          type="target"
          position={Position.Left}
          className="w-2.5 h-2.5 bg-gray-400 border-2 border-white rounded-full -ml-1.5"
        />
      )}

      {/* Header: Tier & Risk Badges */}
      <div className="flex items-center justify-between gap-1.5 mb-2">
        <TierBadge tier={nodeData.tier} size="sm" showIcon />
        <RiskBadge score={nodeData.risk_score} size="sm" />
      </div>

      {/* Center: Supplier Name */}
      <div className="flex items-start gap-2 mb-1.5">
        <div
          className={`w-7 h-7 rounded flex items-center justify-center shrink-0 ${
            isOEM
              ? 'bg-tier-0 text-white'
              : 'bg-brand-100 text-brand-600'
          }`}
        >
          {isOEM ? <ShieldCheck className="w-4 h-4" /> : <Building2 className="w-4 h-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold text-appText leading-tight line-clamp-1" title={nodeData.label}>
            {nodeData.label}
          </p>
          <p className="text-[10px] text-appText-muted mt-0.5">
            {nodeData.region || 'Region Unspecified'}
          </p>
        </div>
      </div>

      {/* Footer: Vulnerability Flags */}
      {nodeData.flags && nodeData.flags.length > 0 && (
        <div className="mt-2 pt-1.5 border-t border-appBorder flex items-center gap-1 text-[10px] text-risk-high">
          <AlertTriangle className="w-3 h-3 text-risk-high shrink-0" />
          <span className="truncate">{nodeData.flags.join(', ')}</span>
        </div>
      )}

      {/* Source handle (material outgoing downstream) */}
      <Handle
        type="source"
        position={Position.Right}
        className="w-2.5 h-2.5 bg-brand-600 border-2 border-white rounded-full -mr-1.5"
      />
    </div>
  );
});

SupplierNode.displayName = 'SupplierNode';
export default SupplierNode;
