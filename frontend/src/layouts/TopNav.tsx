import React from 'react';
import { useLocation } from 'react-router-dom';
import {
  Menu,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  User,
} from 'lucide-react';
import { useHealthCheck } from '../hooks';

interface TopNavProps {
  onToggleMobileSidebar: () => void;
}

const ROUTE_TITLES: Record<string, string> = {
  '/': 'Overview',
  '/dashboard': 'Overview',
  '/suppliers': 'Suppliers',
  '/graph': 'Graph Explorer',
  '/documents': 'Documents',
  '/review': 'Review Queue',
  '/simulate': 'Disruption Simulator',
};

export const TopNav: React.FC<TopNavProps> = ({ onToggleMobileSidebar }) => {
  const location = useLocation();
  const { health, loading, error, refresh } = useHealthCheck(30000);

  const pageTitle = ROUTE_TITLES[location.pathname] || 'TierLens AI';

  return (
    <header className="h-16 bg-surface border-b border-appBorder px-4 sm:px-6 flex items-center justify-between shrink-0 sticky top-0 z-20">
      {/* Left: Mobile hamburger + Page title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleMobileSidebar}
          className="p-1.5 rounded-md text-appText-muted hover:text-appText hover:bg-gray-100 md:hidden"
          aria-label="Open sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div>
          <h2 className="text-base font-semibold text-appText leading-tight">
            {pageTitle}
          </h2>
          <p className="text-xs text-appText-muted hidden sm:block">
            TierLens AI &bull; Automotive Supply Chain
          </p>
        </div>
      </div>

      {/* Right: Health indicator + User profile placeholder */}
      <div className="flex items-center gap-4">
        {/* Connection status badge */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-50 border border-appBorder text-xs">
          {loading ? (
            <>
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              <span className="text-appText-muted hidden sm:inline">Checking connection...</span>
            </>
          ) : error ? (
            <>
              <AlertTriangle className="w-3.5 h-3.5 text-risk-critical" />
              <span className="text-risk-critical font-medium">Backend Offline</span>
            </>
          ) : health?.status === 'ok' ? (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-risk-low" />
              <span className="text-risk-low-text font-medium hidden sm:inline">
                API Connected
              </span>
            </>
          ) : (
            <>
              <AlertTriangle className="w-3.5 h-3.5 text-risk-medium" />
              <span className="text-risk-medium-text font-medium hidden sm:inline">Degraded</span>
            </>
          )}

          <button
            onClick={() => refresh()}
            title="Refresh connection status"
            className="p-0.5 text-appText-faint hover:text-brand-600 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>

        {/* User / Profile Placeholder */}
        <div className="flex items-center gap-2 pl-2 sm:border-l sm:border-appBorder">
          <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-600 font-semibold text-xs flex items-center justify-center border border-brand-500/20">
            <User className="w-4 h-4" />
          </div>
          <div className="hidden lg:block text-left">
            <p className="text-xs font-semibold text-appText leading-tight">Risk Manager</p>
            <p className="text-[10px] text-appText-muted leading-tight">Supply Chain Ops</p>
          </div>
        </div>
      </div>
    </header>
  );
};

export default TopNav;
