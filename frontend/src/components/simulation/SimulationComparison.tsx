import React from 'react';
import { SimulationResponse } from '../../types/simulation';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { SimulationPathView } from './SimulationPathView';
import { formatINR, formatINRExpanded } from '../../utils/currency';
import {
  TrendingDown,
  ShieldCheck,
  AlertTriangle,
  Activity,
  Info,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';

export interface SimulationComparisonProps {
  result: SimulationResponse;
  hasMitigations: boolean;
  onFindAlternatives?: () => void;
}

export const SimulationComparison: React.FC<SimulationComparisonProps> = ({
  result,
  hasMitigations,
  onFindAlternatives,
}) => {
  const { before_mitigation, after_mitigation, improvement, notes } = result;

  const isFullProtection =
    before_mitigation.revenue_at_risk > 0 && after_mitigation.revenue_at_risk === 0;
  const isPartialProtection =
    improvement.revenue_protected > 0 && after_mitigation.revenue_at_risk > 0;
  const isZeroProtection = improvement.revenue_protected === 0;

  // Build merged line map for line-by-line comparison table
  const linesMap = new Map<
    number,
    {
      line_id: number;
      line_name: string;
      daily_revenue: number;
      before_buffer: number | null;
      before_unbuffered: number;
      before_rev: number;
      after_buffer: number | null;
      after_unbuffered: number;
      after_rev: number;
    }
  >();

  (before_mitigation.lines || []).forEach((b) => {
    linesMap.set(b.line_id, {
      line_id: b.line_id,
      line_name: b.line_name,
      daily_revenue: b.daily_revenue,
      before_buffer: b.days_to_impact,
      before_unbuffered: b.unbuffered_days,
      before_rev: b.revenue_at_risk,
      after_buffer: null,
      after_unbuffered: 0,
      after_rev: 0,
    });
  });

  (after_mitigation.lines || []).forEach((a) => {
    const existing = linesMap.get(a.line_id);
    if (existing) {
      existing.after_buffer = a.days_to_impact;
      existing.after_unbuffered = a.unbuffered_days;
      existing.after_rev = a.revenue_at_risk;
    } else {
      linesMap.set(a.line_id, {
        line_id: a.line_id,
        line_name: a.line_name,
        daily_revenue: a.daily_revenue,
        before_buffer: null,
        before_unbuffered: 0,
        before_rev: 0,
        after_buffer: a.days_to_impact,
        after_unbuffered: a.unbuffered_days,
        after_rev: a.revenue_at_risk,
      });
    }
  });

  const mergedLines = Array.from(linesMap.values()).sort((a, b) => a.line_id - b.line_id);

  return (
    <div className="space-y-6">
      {/* 1. Center Improvement Strip / Hero Banner (DESIGN_SYSTEM.md Section 8.7) */}
      <div
        className={`p-4 rounded-lg border transition-all ${isFullProtection
          ? 'bg-emerald-50/80 border-emerald-300 dark:bg-emerald-950/30 dark:border-emerald-800'
          : isPartialProtection
            ? 'bg-amber-50/80 border-amber-300 dark:bg-amber-950/30 dark:border-amber-800'
            : 'bg-surface border-appBorder'
          }`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={`p-2 rounded-full ${isFullProtection
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-300'
                : isPartialProtection
                  ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/60 dark:text-amber-300'
                  : 'bg-gray-100 text-appText-muted dark:bg-gray-800'
                }`}
            >
              {isFullProtection ? (
                <ShieldCheck className="w-5 h-5" />
              ) : (
                <TrendingDown className="w-5 h-5" />
              )}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-appText-muted">
                  Protection Delta
                </span>
                {isFullProtection && (
                  <Badge variant="low" label="100% Disruption Protected" />
                )}
                {isPartialProtection && (
                  <Badge variant="medium" label="Partial Mitigation" />
                )}
                {isZeroProtection && (
                  <Badge variant="neutral" label="Baseline Exposure" />
                )}
              </div>
              <h3 className="text-base sm:text-lg font-bold text-appText mt-0.5">
                {improvement.revenue_protected > 0
                  ? `${formatINRExpanded(improvement.revenue_protected)} Protected`
                  : 'Zero Revenue Protected'}
                {improvement.lines_protected > 0 && (
                  <span className="text-xs font-medium text-appText-muted ml-2">
                    ({improvement.lines_protected} production lines shielded)
                  </span>
                )}
              </h3>
            </div>
          </div>

          {onFindAlternatives && after_mitigation.revenue_at_risk > 0 && (
            <button
              type="button"
              onClick={onFindAlternatives}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-brand-600 hover:bg-brand-500 text-white shadow-sm transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Explore Qualified Alternatives</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. Side-by-Side Impact Cards: Before vs After Mitigation */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Before Mitigation (Baseline Outage) */}
        <Card className="border-red-200 dark:border-red-950/60 shadow-xs">
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-appBorder/60 pb-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-risk-critical" />
                <h3 className="text-sm font-semibold text-appText">
                  Before Mitigation (Baseline Outage)
                </h3>
              </div>
              <Badge variant="critical">Unmitigated</Badge>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-3 gap-2">
              <div className="p-2.5 rounded bg-appBg/40 border border-appBorder/60">
                <span className="text-[11px] font-medium text-appText-muted block">
                  Revenue at Risk
                </span>
                <span className="text-sm font-bold font-mono text-risk-critical">
                  {formatINR(before_mitigation.revenue_at_risk)}
                </span>
              </div>
              <div className="p-2.5 rounded bg-appBg/40 border border-appBorder/60">
                <span className="text-[11px] font-medium text-appText-muted block">
                  Lines at Risk
                </span>
                <span className="text-sm font-bold font-mono text-appText">
                  {before_mitigation.lines_at_risk}
                </span>
              </div>
              <div className="p-2.5 rounded bg-appBg/40 border border-appBorder/60">
                <span className="text-[11px] font-medium text-appText-muted block">
                  Days to Impact
                </span>
                <span className="text-sm font-bold font-mono text-appText">
                  {before_mitigation.days_to_impact !== null
                    ? `${before_mitigation.days_to_impact}d`
                    : 'None'}
                </span>
              </div>
            </div>

            {/* Primary Affected Path */}
            <div>
              <span className="text-xs font-medium text-appText-muted block mb-1">
                Disrupted Flow Path:
              </span>
              <SimulationPathView
                path={before_mitigation.affected_path}
                daysToImpact={before_mitigation.days_to_impact}
              />
            </div>
          </div>
        </Card>

        {/* After Mitigation (Mitigated State) */}
        <Card
          className={`shadow-xs ${after_mitigation.revenue_at_risk === 0
            ? 'border-emerald-300 dark:border-emerald-950/60'
            : 'border-brand-500/30'
            }`}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-appBorder/60 pb-3">
              <div className="flex items-center gap-2">
                <CheckCircle2
                  className={`w-4 h-4 ${after_mitigation.revenue_at_risk === 0
                    ? 'text-emerald-600'
                    : 'text-brand-600'
                    }`}
                />
                <h3 className="text-sm font-semibold text-appText">
                  After Mitigation (What-If State)
                </h3>
              </div>
              <Badge
                variant={
                  !hasMitigations
                    ? 'neutral'
                    : after_mitigation.revenue_at_risk === 0
                      ? 'low'
                      : 'medium'
                }
              >
                {!hasMitigations
                  ? 'Unmitigated'
                  : after_mitigation.revenue_at_risk === 0
                    ? 'Protected'
                    : 'Mitigated'}
              </Badge>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-3 gap-2">
              <div className="p-2.5 rounded bg-appBg/40 border border-appBorder/60">
                <span className="text-[11px] font-medium text-appText-muted block">
                  Remaining Risk
                </span>
                <span
                  className={`text-sm font-bold font-mono ${after_mitigation.revenue_at_risk === 0
                    ? 'text-emerald-600'
                    : 'text-amber-600'
                    }`}
                >
                  {formatINR(after_mitigation.revenue_at_risk)}
                </span>
              </div>
              <div className="p-2.5 rounded bg-appBg/40 border border-appBorder/60">
                <span className="text-[11px] font-medium text-appText-muted block">
                  Lines at Risk
                </span>
                <span className="text-sm font-bold font-mono text-appText">
                  {after_mitigation.lines_at_risk}
                </span>
              </div>
              <div className="p-2.5 rounded bg-appBg/40 border border-appBorder/60">
                <span className="text-[11px] font-medium text-appText-muted block">
                  Days to Impact
                </span>
                <span className="text-sm font-bold font-mono text-appText">
                  {after_mitigation.days_to_impact !== null
                    ? `${after_mitigation.days_to_impact}d`
                    : 'Absorbed'}
                </span>
              </div>
            </div>

            {/* Mitigated Path */}
            <div>
              <span className="text-xs font-medium text-appText-muted block mb-1">
                Residual Disrupted Path:
              </span>
              <SimulationPathView
                path={after_mitigation.affected_path}
                daysToImpact={after_mitigation.days_to_impact}
              />
            </div>
          </div>
        </Card>
      </div>

      {/* 3. Production Line Breakdown Table */}
      <Card>
        <div className="space-y-3">
          <div className="flex items-center justify-between border-b border-appBorder pb-2.5">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-brand-600" />
              <h3 className="text-sm font-semibold text-appText">
                Production Line Impact & Downtime Breakdown
              </h3>
            </div>
            <span className="text-xs text-appText-muted">
              {mergedLines.length} lines evaluated
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-appText">
              <thead className="bg-appBg/60 border-b border-appBorder text-appText-muted uppercase tracking-wider font-semibold text-[10px]">
                <tr>
                  <th className="py-2.5 px-3">Production Line</th>
                  <th className="py-2.5 px-3">Daily Revenue</th>
                  <th className="py-2.5 px-3 text-center">Days to Impact (B/A)</th>
                  <th className="py-2.5 px-3 text-center">Downtime Days (B/A)</th>
                  <th className="py-2.5 px-3 text-right">Exposure Before</th>
                  <th className="py-2.5 px-3 text-right">Exposure After</th>
                  <th className="py-2.5 px-3 text-right font-bold text-emerald-600">
                    Protected
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-appBorder/50 font-mono">
                {mergedLines.map((row) => {
                  const protectedAmt = Math.max(0, row.before_rev - row.after_rev);

                  return (
                    <tr
                      key={row.line_id}
                      className="hover:bg-appBg/30 transition-colors"
                    >
                      <td className="py-2.5 px-3 font-sans font-medium text-appText flex items-center gap-1.5">
                        <Activity className="w-3.5 h-3.5 text-appText-muted" />
                        <span>{row.line_name}</span>
                      </td>
                      <td className="py-2.5 px-3 text-appText-muted">
                        {formatINR(row.daily_revenue)}/d
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="text-appText-muted">
                          {row.before_buffer !== null ? `${row.before_buffer}d` : '-'}
                        </span>
                        <span className="text-appText-faint mx-1.5">→</span>
                        <span
                          className={`font-semibold ${(row.after_buffer || 0) > (row.before_buffer || 0)
                            ? 'text-emerald-600 font-bold'
                            : 'text-appText'
                            }`}
                        >
                          {row.after_buffer !== null ? `${row.after_buffer}d` : 'Absorbed'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="text-risk-critical">
                          {row.before_unbuffered}d
                        </span>
                        <span className="text-appText-faint mx-1.5">→</span>
                        <span
                          className={
                            row.after_unbuffered < row.before_unbuffered
                              ? 'text-emerald-600 font-bold'
                              : 'text-appText'
                          }
                        >
                          {row.after_unbuffered}d
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right text-risk-critical">
                        {formatINR(row.before_rev)}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-medium ${row.after_rev === 0
                          ? 'text-emerald-600'
                          : 'text-amber-600'
                          }`}
                      >
                        {formatINR(row.after_rev)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-bold text-emerald-600">
                        {protectedAmt > 0 ? `+${formatINR(protectedAmt)}` : '₹0'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </Card>

      {/* 4. Simulation Notes & Disclosures */}
      {notes && notes.length > 0 && (
        <Card className="bg-appBg/30 border-appBorder/70">
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <Info className="w-4 h-4 text-brand-600" />
              <h4 className="text-xs font-semibold text-appText uppercase tracking-wider">
                Simulation Engine Notes & Disclosures
              </h4>
            </div>
            <ul className="space-y-1.5 pl-5 list-disc text-xs text-appText-muted">
              {notes.map((note, idx) => (
                <li key={idx} className="leading-relaxed">
                  {note}
                </li>
              ))}
            </ul>
          </div>
        </Card>
      )}
    </div>
  );
};

export default SimulationComparison;
