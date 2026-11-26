import React, { useEffect, useState } from 'react';
import {
  DocumentDetailResponse,
  DocumentEvidenceResponse,
  DocumentEvidenceItem,
} from '../../types/document';
import { getDocumentDetail, getDocumentEvidence } from '../../services/documentService';
import { StatusBadge } from '../common/StatusBadge';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { Button } from '../common/Button';
import {
  X,
  FileText,
  FileCode,
  FileSpreadsheet,
  Quote,
  Layers,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  AlertCircle,
  AlertTriangle,
  Network,
  Users,
} from 'lucide-react';

interface DocumentEvidenceDrawerProps {
  documentId: number | null;
  isOpen: boolean;
  onClose: () => void;
}

export const DocumentEvidenceDrawer: React.FC<DocumentEvidenceDrawerProps> = ({
  documentId,
  isOpen,
  onClose,
}) => {
  const [detail, setDetail] = useState<DocumentDetailResponse | null>(null);
  const [evidenceData, setEvidenceData] = useState<DocumentEvidenceResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !documentId) {
      setDetail(null);
      setEvidenceData(null);
      setError(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    Promise.all([
      getDocumentDetail(documentId),
      getDocumentEvidence(documentId),
    ])
      .then(([detailRes, evidenceRes]) => {
        if (!isMounted) return;
        setDetail(detailRes);
        setEvidenceData(evidenceRes);
      })
      .catch((err: any) => {
        if (!isMounted) return;
        console.error(`Failed to load document details for ID ${documentId}:`, err);
        setError(err?.message || 'Failed to load document details from server.');
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, documentId]);

  if (!isOpen) return null;

  const formatDate = (isoString?: string) => {
    if (!isoString) return 'N/A';
    try {
      const d = new Date(isoString);
      return d.toLocaleString('en-GB', {
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

  const formatDocType = (type?: string) => {
    if (!type) return 'Unknown';
    return type
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  const getFileIcon = (filename?: string) => {
    if (!filename) return <FileText className="w-5 h-5 text-gray-500" />;
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return <FileText className="w-5 h-5 text-red-500" />;
    if (ext === 'csv') return <FileSpreadsheet className="w-5 h-5 text-emerald-600" />;
    return <FileCode className="w-5 h-5 text-blue-500" />;
  };

  const getConfidenceBadge = (conf?: number | null) => {
    if (conf === null || conf === undefined) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 border border-gray-300">
          <AlertCircle className="w-3 h-3 text-gray-500" />
          Unscored
        </span>
      );
    }
    const pct = Math.round(conf * 100);
    if (conf >= 0.85) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-300">
          <ShieldCheck className="w-3 h-3 text-emerald-600" />
          {pct}% High
        </span>
      );
    }
    if (conf >= 0.7) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-300">
          <Sparkles className="w-3 h-3 text-amber-600" />
          {pct}% Medium
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-300">
        <AlertCircle className="w-3 h-3 text-red-600" />
        {pct}% Low
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/30 backdrop-blur-xs flex justify-end">
      <div className="relative w-full max-w-xl bg-white h-full shadow-2xl border-l border-appBorder flex flex-col animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-appBorder bg-gray-50/80 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <div className="w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center shrink-0 mt-0.5 shadow-xs">
              {getFileIcon(detail?.filename)}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base font-bold text-appText truncate">
                  {detail?.filename || `Document #${documentId}`}
                </h3>
                {detail && (
                  <StatusBadge status={detail.extraction_status} size="sm" />
                )}
              </div>
              <div className="flex items-center gap-2 mt-1 text-xs text-appText-muted flex-wrap">
                <span className="inline-flex items-center font-medium bg-gray-100 text-gray-700 px-2 py-0.5 rounded border border-gray-200">
                  {formatDocType(detail?.doc_type)}
                </span>
                {detail?.page_count !== null && detail?.page_count !== undefined && (
                  <span>• {detail.page_count} page{detail.page_count === 1 ? '' : 's'}</span>
                )}
                <span>• Uploaded {formatDate(detail?.uploaded_at)}</span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-appText-muted hover:text-appText p-1.5 rounded-lg hover:bg-gray-100 transition-colors shrink-0"
            title="Close Drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading ? (
            <div className="py-20 flex flex-col items-center justify-center">
              <LoadingSpinner size="lg" label="Loading document details and evidence..." />
            </div>
          ) : error ? (
            <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto">
                <AlertCircle className="w-5 h-5" />
              </div>
              <h4 className="text-sm font-semibold text-red-900">
                Failed to Load Document
              </h4>
              <p className="text-xs text-red-700 max-w-sm mx-auto">{error}</p>
            </div>
          ) : detail ? (
            <>
              {/* Processing Statistics Strip */}
              <div>
                <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2.5">
                  Extraction Statistics
                </h4>
                <div className="grid grid-cols-3 gap-2.5">
                  <div className="bg-blue-50/60 border border-blue-200/80 rounded-xl p-3">
                    <div className="flex items-center gap-1.5 text-xs text-blue-700 font-medium">
                      <Users className="w-3.5 h-3.5 text-blue-600" />
                      Entities
                    </div>
                    <div className="text-xl font-bold text-blue-900 mt-1">
                      {detail.stats.entities}
                    </div>
                  </div>

                  <div className="bg-emerald-50/60 border border-emerald-200/80 rounded-xl p-3">
                    <div className="flex items-center gap-1.5 text-xs text-emerald-700 font-medium">
                      <Network className="w-3.5 h-3.5 text-emerald-600" />
                      Relationships
                    </div>
                    <div className="text-xl font-bold text-emerald-900 mt-1">
                      {detail.stats.relationships}
                    </div>
                  </div>

                  <div
                    className={`border rounded-xl p-3 ${
                      detail.stats.low_confidence > 0
                        ? 'bg-amber-50/60 border-amber-200/80 text-amber-900'
                        : 'bg-gray-50 border-gray-200 text-gray-700'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 text-xs font-medium">
                      <AlertTriangle
                        className={`w-3.5 h-3.5 ${
                          detail.stats.low_confidence > 0
                            ? 'text-amber-600'
                            : 'text-gray-400'
                        }`}
                      />
                      Low Confidence
                    </div>
                    <div
                      className={`text-xl font-bold mt-1 ${
                        detail.stats.low_confidence > 0
                          ? 'text-amber-800'
                          : 'text-gray-800'
                      }`}
                    >
                      {detail.stats.low_confidence}
                    </div>
                  </div>
                </div>
              </div>

              {/* Extracted Evidence Snippets */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                    Extracted Evidence Snippets ({evidenceData?.evidence.length || 0})
                  </h4>
                </div>

                {!evidenceData || evidenceData.evidence.length === 0 ? (
                  <div className="p-8 bg-gray-50 rounded-xl border border-dashed border-gray-300 text-center">
                    <div className="w-10 h-10 rounded-full bg-gray-200/60 text-gray-500 flex items-center justify-center mx-auto mb-2">
                      <FileText className="w-5 h-5" />
                    </div>
                    <p className="text-sm font-medium text-appText">
                      No Evidence Snippets Found
                    </p>
                    <p className="text-xs text-appText-muted max-w-xs mx-auto mt-1">
                      This document has not produced any extracted evidence snippets yet, or extraction is still pending.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3.5">
                    {evidenceData.evidence.map((item: DocumentEvidenceItem, index: number) => (
                      <div
                        key={item.id}
                        className="bg-white rounded-xl border border-appBorder shadow-2xs hover:shadow-xs transition-shadow p-4 space-y-3"
                      >
                        {/* Snippet Header */}
                        <div className="flex items-center justify-between text-xs text-appText-muted border-b border-gray-100 pb-2">
                          <span className="font-semibold text-gray-700">
                            Snippet #{index + 1}
                            {item.page !== null && item.page !== undefined && (
                              <span className="font-normal text-gray-500 ml-1.5">
                                (Page {item.page})
                              </span>
                            )}
                          </span>
                          {getConfidenceBadge(item.llm_confidence)}
                        </div>

                        {/* Verbatim Snippet Box */}
                        <div className="p-3 bg-gray-50/80 rounded-lg border border-gray-200 text-xs text-gray-800 flex items-start gap-2.5">
                          <Quote className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
                          <p className="italic leading-relaxed">
                            "{item.snippet}"
                          </p>
                        </div>

                        {/* Linked Relationship Ref */}
                        {item.relationship ? (
                          <div className="bg-brand-50/40 border border-brand-500/10 rounded-lg p-2.5 text-xs flex items-center justify-between flex-wrap gap-2">
                            <div className="flex items-center gap-1.5 font-medium text-appText">
                              <span className="font-semibold text-brand-600">
                                {item.relationship.supplier}
                              </span>
                              <ArrowRight className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                              <span className="font-semibold text-appText">
                                {item.relationship.buyer}
                              </span>
                            </div>
                            <span className="inline-flex items-center gap-1 bg-white px-2 py-0.5 rounded text-[11px] font-medium text-teal-700 border border-teal-200 shadow-2xs">
                              <Layers className="w-3 h-3 text-teal-600" />
                              {item.relationship.material}
                            </span>
                          </div>
                        ) : (
                          <div className="text-[11px] text-gray-400 italic">
                            No direct relationship mapped to this snippet.
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-appBorder bg-gray-50/80 flex items-center justify-end">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
