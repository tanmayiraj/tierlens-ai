import React from 'react';
import { Card, Button } from '../components';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Card className="max-w-md text-center p-8">
        <h2 className="text-4xl font-extrabold text-brand-600 mb-2">404</h2>
        <h3 className="text-lg font-bold text-appText mb-1">Page Not Found</h3>
        <p className="text-sm text-appText-muted mb-6">
          The page you requested does not exist or has been moved.
        </p>
        <Link to="/">
          <Button variant="primary" size="sm">
            <ArrowLeft className="w-4 h-4 mr-1.5" /> Return to Dashboard
          </Button>
        </Link>
      </Card>
    </div>
  );
};

export default NotFoundPage;
