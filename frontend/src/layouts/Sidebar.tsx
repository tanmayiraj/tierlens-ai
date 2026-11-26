import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Building2,
  Network,
  FileText,
  CheckSquare,
  FlaskConical,
  Layers,
  X,
} from 'lucide-react';

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

const NAV_ITEMS = [
  { name: 'Overview', path: '/', icon: LayoutDashboard },
  { name: 'Suppliers', path: '/suppliers', icon: Building2 },
  { name: 'Graph Explorer', path: '/graph', icon: Network },
  { name: 'Documents', path: '/documents', icon: FileText },
  { name: 'Review Queue', path: '/review', icon: CheckSquare },
  { name: 'Disruption Simulator', path: '/simulate', icon: FlaskConical },
];

export const Sidebar: React.FC<SidebarProps> = ({ isOpen = false, onClose }) => {
  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden transition-opacity"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-surface border-r border-appBorder flex flex-col shrink-0 h-screen transition-transform duration-200 ease-out md:translate-x-0 md:static md:z-auto ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand & Logo Header */}
        <div className="h-16 px-5 flex items-center justify-between border-b border-appBorder shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center text-white shadow-sm ring-1 ring-brand-500/20">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight text-appText leading-tight">
                TierLens <span className="text-brand-600">AI</span>
              </h1>
              <p className="text-[11px] text-appText-muted font-medium">Risk Intelligence</p>
            </div>
          </div>

          {/* Mobile close button */}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded-md text-appText-muted hover:text-appText hover:bg-gray-100 md:hidden"
              aria-label="Close menu"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Navigation list */}
        <nav className="p-3 space-y-1 flex-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-brand-100 text-brand-600 font-semibold'
                      : 'text-appText-muted hover:bg-gray-100 hover:text-appText'
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Footer Info */}
        <div className="p-4 border-t border-appBorder text-xs text-appText-muted">
          <div className="flex items-center justify-between">
            <span className="font-medium text-appText">TierLens AI</span>
            <span className="px-1.5 py-0.5 rounded bg-gray-100 text-[10px] text-appText-muted font-mono">
              v0.1.0
            </span>
          </div>
          <p className="text-[11px] text-appText-faint mt-1">Multi-Level Supplier Risk</p>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
