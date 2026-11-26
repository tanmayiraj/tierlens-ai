import React from 'react';
import { ArrowRight, AlertTriangle, Factory, Activity } from 'lucide-react';

export interface SimulationPathViewProps {
  path: string[];
  daysToImpact?: number | null;
  className?: string;
}

export const SimulationPathView: React.FC<SimulationPathViewProps> = ({
  path,
  daysToImpact,
  className = '',
}) => {
  if (!path || path.length === 0) {
    return (
      <div className={`p-3 bg-appBg/40 rounded border border-dashed border-appBorder text-center ${className}`}>
        <span className="text-xs text-appText-muted">
          No downstream production line disrupted (exposure absorbed by buffer).
        </span>
      </div>
    );
  }

  return (
    <div className={`overflow-x-auto py-2 ${className}`}>
      <div className="flex items-center gap-1.5 min-w-max">
        {path.map((nodeName, idx) => {
          const isOrigin = idx === 0;
          const isTerminalLine = idx === path.length - 1;

          return (
            <React.Fragment key={idx}>
              {/* Node Pill */}
              <div
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs font-medium shadow-2xs ${
                  isOrigin
                    ? 'bg-red-50 text-risk-critical border-red-300 dark:bg-red-950/40 dark:border-red-900/50'
                    : isTerminalLine
                    ? 'bg-amber-50 text-amber-900 border-amber-300 dark:bg-amber-950/40 dark:text-amber-200 dark:border-amber-800/50'
                    : 'bg-surface text-appText border-appBorder'
                }`}
              >
                {isOrigin ? (
                  <AlertTriangle className="w-3.5 h-3.5 text-risk-critical shrink-0" />
                ) : isTerminalLine ? (
                  <Activity className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                ) : (
                  <Factory className="w-3.5 h-3.5 text-appText-muted shrink-0" />
                )}
                <span className="truncate max-w-[140px]">{nodeName}</span>
                {isTerminalLine && daysToImpact !== undefined && daysToImpact !== null && (
                  <span className="text-[10px] font-mono font-bold bg-amber-200/60 dark:bg-amber-900/60 px-1 py-0.2 rounded ml-1 text-amber-900 dark:text-amber-100">
                    Day {daysToImpact}
                  </span>
                )}
              </div>

              {/* Flow Connector Arrow */}
              {!isTerminalLine && (
                <div className="flex items-center justify-center text-appText-muted px-0.5">
                  <ArrowRight className="w-3.5 h-3.5 text-appText-muted/70" />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

export default SimulationPathView;
