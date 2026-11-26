import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopNav from './TopNav';

export const MainLayout: React.FC = () => {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-appBg">
      {/* Sidebar with responsive mobile drawer support */}
      <Sidebar
        isOpen={isMobileSidebarOpen}
        onClose={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main column */}
      <div className="flex flex-col flex-1 overflow-hidden min-w-0">
        <TopNav onToggleMobileSidebar={() => setIsMobileSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default MainLayout;
