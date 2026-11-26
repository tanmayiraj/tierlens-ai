import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import {
  DashboardPage,
  SuppliersPage,
  GraphPage,
  DocumentsPage,
  ReviewQueuePage,
  SimulationPage,
  NotFoundPage,
} from './pages';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="dashboard" element={<Navigate to="/" replace />} />
          <Route path="suppliers" element={<SuppliersPage />} />
          <Route path="graph" element={<GraphPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="review" element={<ReviewQueuePage />} />
          <Route path="simulate" element={<SimulationPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
