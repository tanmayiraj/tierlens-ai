import React from 'react';
import { DocumentListItem } from '../../types/document';
import { StatusBadge } from '../common/StatusBadge';
import { Button } from '../common/Button';
import {
  FileText,
  FileCode,
  FileSpreadsheet,
  Network,
  Eye,
  Calendar,
} from 'lucide-react';

interface DocumentTableProps {
  documents: DocumentListItem[];
  onSelectDocument: (id: number) => void;
}

export const DocumentTable: React.FC<DocumentTableProps> = ({
  documents,
  onSelectDocument,
}) => {
  const formatDocType = (type?: string) => {
    if (!type) return 'Unknown';
    return type
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') {
      return (
        <div className="w-8 h-8 rounded-lg bg-red-50 text-red-600 flex items-center justify-center shrink-0 border border-red-200">
          <FileText className="w-4 h-4" />
        </div>
      );
    }
    if (ext === 'csv') {
      return (
        <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0 border border-emerald-200">
          <FileSpreadsheet className="w-4 h-4" />
        </div>
      );
    }
    return (
      <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0 border border-blue-200">
        <FileCode className="w-4 h-4" />
      </div>
    );
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-50/80 text-xs font-semibold text-appText-muted border-b border-appBorder">
          <tr>
            <th className="py-3 px-4">Document</th>
            <th className="py-3 px-4">Document Type</th>
            <th className="py-3 px-4">Upload Date</th>
            <th className="py-3 px-4">Relationships</th>
            <th className="py-3 px-4">Status</th>
            <th className="py-3 px-4 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {documents.map((doc) => (
            <tr
              key={doc.id}
              onClick={() => onSelectDocument(doc.id)}
              className="hover:bg-brand-50/30 cursor-pointer transition-colors group"
            >
              {/* Document Filename & ID */}
              <td className="py-3 px-4">
                <div className="flex items-center gap-3">
                  {getFileIcon(doc.filename)}
                  <div className="min-w-0">
                    <span className="font-semibold text-appText group-hover:text-brand-600 transition-colors block truncate max-w-xs sm:max-w-md">
                      {doc.filename}
                    </span>
                    <span className="text-[11px] text-appText-muted block">
                      ID #{doc.id}
                    </span>
                  </div>
                </div>
              </td>

              {/* Document Type */}
              <td className="py-3 px-4 whitespace-nowrap">
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200">
                  {formatDocType(doc.doc_type)}
                </span>
              </td>

              {/* Upload Date */}
              <td className="py-3 px-4 whitespace-nowrap text-xs text-appText-muted">
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-gray-400" />
                  <span>{formatDate(doc.uploaded_at)}</span>
                </div>
              </td>

              {/* Relationships Found */}
              <td className="py-3 px-4 whitespace-nowrap">
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    doc.relationships_found > 0
                      ? 'bg-blue-50 text-blue-700 border border-blue-200'
                      : 'bg-gray-100 text-gray-600 border border-gray-200'
                  }`}
                >
                  <Network className="w-3 h-3" />
                  {doc.relationships_found} found
                </span>
              </td>

              {/* Status */}
              <td className="py-3 px-4 whitespace-nowrap">
                <StatusBadge status={doc.extraction_status} size="sm" />
              </td>

              {/* Actions */}
              <td className="py-3 px-4 text-right whitespace-nowrap">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectDocument(doc.id);
                  }}
                  icon={<Eye className="w-3.5 h-3.5" />}
                  className="text-brand-600 hover:text-brand-700 hover:bg-brand-50"
                >
                  View Evidence
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
