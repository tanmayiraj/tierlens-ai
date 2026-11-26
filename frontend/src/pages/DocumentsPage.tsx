import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  DocumentListItem,
  DocumentQueryParams,
} from '../types/document';
import {
  getDocuments,
  uploadDocuments,
  loadSamples,
} from '../services/documentService';
import {
  Button,
  Card,
  LoadingSpinner,
  DocumentTable,
  DocumentUploadModal,
  DocumentEvidenceDrawer,
} from '../components';
import {
  FileText,
  Upload,
  FolderUp,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  X,
  Network,
  Clock,
  Filter,
  ChevronLeft,
  ChevronRight,
  Database,
} from 'lucide-react';

export const DocumentsPage: React.FC = () => {
  // Data State
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  // Pagination
  const [limit, setLimit] = useState<number>(25);
  const [offset, setOffset] = useState<number>(0);

  // Modals & Drawers
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isLoadingSamples, setIsLoadingSamples] = useState<boolean>(false);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);

  // Fetch Documents
  const fetchDocList = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: DocumentQueryParams = {
        limit,
        offset,
      };
      if (statusFilter !== 'all') {
        params.extraction_status = statusFilter;
      }
      if (typeFilter !== 'all') {
        params.doc_type = typeFilter;
      }

      const res = await getDocuments(params);
      setDocuments(res.items || []);
      setTotalCount(res.total || 0);
    } catch (err: any) {
      console.error('Failed to load documents:', err);
      setError(err?.message || 'Failed to load documents from backend.');
    } finally {
      setIsLoading(false);
    }
  }, [limit, offset, statusFilter, typeFilter]);

  useEffect(() => {
    fetchDocList();
  }, [fetchDocList]);

  // Handle Load Samples
  const handleLoadSamples = async () => {
    setIsLoadingSamples(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await loadSamples();
      setSuccessMessage(
        `Successfully loaded ${res.loaded} sample documents. Extraction pipeline processed ${res.queued_for_extraction} items.`
      );
      setOffset(0);
      await fetchDocList();
    } catch (err: any) {
      console.error('Failed to load sample documents:', err);
      setError(err?.message || 'Failed to load sample documents.');
    } finally {
      setIsLoadingSamples(false);
    }
  };

  // Handle Upload
  const handleUploadFiles = async (files: File[], docType?: string) => {
    setIsUploading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await uploadDocuments(files, docType);
      const count = res.documents?.length || files.length;
      setSuccessMessage(
        `Successfully uploaded ${count} document${count === 1 ? '' : 's'}. Initialized extraction pipeline.`
      );
      setIsUploadModalOpen(false);
      setOffset(0);
      await fetchDocList();
    } catch (err: any) {
      console.error('Failed to upload documents:', err);
      setError(err?.message || 'Failed to upload documents.');
    } finally {
      setIsUploading(false);
    }
  };

  // Client-side Search on current page items
  const filteredDocuments = useMemo(() => {
    if (!searchQuery.trim()) return documents;
    const q = searchQuery.toLowerCase().trim();
    return documents.filter(
      (doc) =>
        doc.filename.toLowerCase().includes(q) ||
        doc.doc_type.toLowerCase().includes(q)
    );
  }, [documents, searchQuery]);

  // KPI Statistics Strip (Computed over current list or total)
  const stats = useMemo(() => {
    const total = totalCount;
    const done = documents.filter((d) => d.extraction_status === 'done').length;
    const pendingOrProcessing = documents.filter(
      (d) => d.extraction_status === 'pending' || d.extraction_status === 'processing'
    ).length;
    const totalRelationships = documents.reduce(
      (acc, d) => acc + (d.relationships_found || 0),
      0
    );
    return { total, done, pendingOrProcessing, totalRelationships };
  }, [documents, totalCount]);

  // Pagination bounds
  const startItem = offset + 1;
  const endItem = Math.min(offset + limit, totalCount);
  const hasPrevPage = offset > 0;
  const hasNextPage = offset + limit < totalCount;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-appText">
              Document Management
            </h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-100 text-brand-600 border border-brand-500/20">
              {totalCount} Documents
            </span>
          </div>
          <p className="text-sm text-appText-muted mt-1">
            Procurement document ingestion, AI relationship extraction, and evidence snippets.
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2.5 flex-wrap">
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchDocList}
            disabled={isLoading || isLoadingSamples || isUploading}
            icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleLoadSamples}
            disabled={isLoadingSamples || isUploading}
            isLoading={isLoadingSamples}
            icon={<FolderUp className="w-3.5 h-3.5" />}
          >
            Load Samples
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsUploadModalOpen(true)}
            disabled={isUploading || isLoadingSamples}
            icon={<Upload className="w-3.5 h-3.5" />}
          >
            Upload Document
          </Button>
        </div>
      </div>

      {/* Success Notification Banner */}
      {successMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between gap-3 text-sm text-emerald-800 animate-in fade-in duration-150">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMessage}</span>
          </div>
          <button
            onClick={() => setSuccessMessage(null)}
            className="text-emerald-500 hover:text-emerald-700 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Error Alert Banner */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between gap-3 text-sm text-red-800 animate-in fade-in duration-150">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-red-500 hover:text-red-700 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600 shrink-0">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-appText">{stats.total}</div>
            <div className="text-xs text-appText-muted font-medium">Total Ingested</div>
          </div>
        </Card>

        <Card className="p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600 shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-emerald-700">{stats.done}</div>
            <div className="text-xs text-appText-muted font-medium">Fully Extracted</div>
          </div>
        </Card>

        <Card className="p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600 shrink-0">
            <Clock className="w-4 h-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-amber-700">
              {stats.pendingOrProcessing}
            </div>
            <div className="text-xs text-appText-muted font-medium">In Pipeline</div>
          </div>
        </Card>

        <Card className="p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-purple-50 flex items-center justify-center text-purple-600 shrink-0">
            <Network className="w-4 h-4" />
          </div>
          <div>
            <div className="text-lg font-bold text-purple-700">
              {stats.totalRelationships}
            </div>
            <div className="text-xs text-appText-muted font-medium">Relationships Found</div>
          </div>
        </Card>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-white p-3.5 rounded-xl border border-appBorder">
        {/* Search Input */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-appText-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by filename or document type..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full text-sm pl-9 pr-4 py-2 bg-gray-50 border border-appBorder rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-500 focus:bg-white transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Status Filter */}
          <div className="flex items-center gap-1.5 text-xs text-appText-muted">
            <Filter className="w-3.5 h-3.5 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setOffset(0);
              }}
              className="text-xs py-1.5 px-2 bg-gray-50 border border-appBorder rounded-md text-appText font-medium focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="all">All Statuses</option>
              <option value="done">Done</option>
              <option value="processing">Processing</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          {/* Document Type Filter */}
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setOffset(0);
            }}
            className="text-xs py-1.5 px-2 bg-gray-50 border border-appBorder rounded-md text-appText font-medium focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="all">All Types</option>
            <option value="purchase_order">Purchase Order</option>
            <option value="contract">Contract</option>
            <option value="invoice">Invoice</option>
            <option value="procurement_note">Procurement Note</option>
            <option value="supplier_record">Supplier Record</option>
          </select>

          {/* Clear Filters Button */}
          {(statusFilter !== 'all' || typeFilter !== 'all' || searchQuery) && (
            <button
              onClick={() => {
                setStatusFilter('all');
                setTypeFilter('all');
                setSearchQuery('');
                setOffset(0);
              }}
              className="text-xs text-brand-600 hover:text-brand-700 font-medium px-2 py-1 rounded hover:bg-brand-50 transition-colors"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <Card className="py-20 text-center">
          <LoadingSpinner size="lg" label="Loading documents from repository..." />
        </Card>
      ) : totalCount === 0 ? (
        /* Empty State */
        <Card className="py-16 text-center border-dashed">
          <div className="w-16 h-16 rounded-full bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-600 mx-auto mb-4">
            <FileText className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-appText">
            No Documents Ingested Yet
          </h3>
          <p className="text-sm text-appText-muted max-w-md mx-auto mt-1.5 mb-6">
            Upload procurement documents (PDF, TXT, CSV) or load the bundled synthetic sample dataset to trigger entity and relationship extraction.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleLoadSamples}
              isLoading={isLoadingSamples}
              icon={<FolderUp className="w-3.5 h-3.5" />}
            >
              Load Sample Dataset
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsUploadModalOpen(true)}
              icon={<Upload className="w-3.5 h-3.5" />}
            >
              Upload Document
            </Button>
          </div>
        </Card>
      ) : filteredDocuments.length === 0 ? (
        /* Filter No Match State */
        <Card className="py-12 text-center border-dashed">
          <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center text-gray-500 mx-auto mb-3">
            <Search className="w-6 h-6" />
          </div>
          <h4 className="text-base font-semibold text-appText">
            No matching documents found
          </h4>
          <p className="text-xs text-appText-muted mt-1 mb-4">
            No documents matched your current search and filter criteria.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setSearchQuery('');
              setStatusFilter('all');
              setTypeFilter('all');
              setOffset(0);
            }}
          >
            Clear Filters
          </Button>
        </Card>
      ) : (
        /* Documents Table Card */
        <Card className="overflow-hidden p-0">
          <DocumentTable
            documents={filteredDocuments}
            onSelectDocument={(id) => setSelectedDocId(id)}
          />

          {/* Pagination Footer */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 bg-gray-50/60 border-t border-appBorder text-xs text-appText-muted">
            <div>
              Showing <span className="font-semibold text-appText">{startItem}</span> to{' '}
              <span className="font-semibold text-appText">{endItem}</span> of{' '}
              <span className="font-semibold text-appText">{totalCount}</span> documents
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <span>Rows per page:</span>
                <select
                  value={limit}
                  onChange={(e) => {
                    setLimit(Number(e.target.value));
                    setOffset(0);
                  }}
                  className="px-2 py-1 text-xs font-medium bg-white border border-appBorder rounded text-appText focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
              </div>

              <div className="flex items-center gap-1">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!hasPrevPage}
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  icon={<ChevronLeft className="w-3.5 h-3.5" />}
                  className="px-2"
                >
                  Prev
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!hasNextPage}
                  onClick={() => setOffset(offset + limit)}
                  className="px-2 flex items-center gap-1"
                >
                  <span>Next</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Upload Document Modal */}
      <DocumentUploadModal
        isOpen={isUploadModalOpen}
        isUploading={isUploading}
        onClose={() => setIsUploadModalOpen(false)}
        onUpload={handleUploadFiles}
      />

      {/* Document Detail & Evidence Drawer */}
      <DocumentEvidenceDrawer
        documentId={selectedDocId}
        isOpen={selectedDocId !== null}
        onClose={() => setSelectedDocId(null)}
      />
    </div>
  );
};

export default DocumentsPage;
