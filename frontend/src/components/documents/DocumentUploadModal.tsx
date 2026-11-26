import React, { useState, useRef } from 'react';
import { Button } from '../common/Button';
import {
  X,
  Upload,
  FileText,
  FileCode,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle2,
  Trash2,
} from 'lucide-react';

interface DocumentUploadModalProps {
  isOpen: boolean;
  isUploading: boolean;
  onClose: () => void;
  onUpload: (files: File[], docType?: string) => Promise<void>;
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.csv'];

export const DocumentUploadModal: React.FC<DocumentUploadModalProps> = ({
  isOpen,
  isUploading,
  onClose,
  onUpload,
}) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [docType, setDocType] = useState<string>('auto');
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const validateAndAddFiles = (files: FileList | File[]) => {
    setValidationError(null);
    const newFiles: File[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();

      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        setValidationError(
          `File "${file.name}" has an unsupported format. Allowed formats: PDF, TXT, CSV.`
        );
        return;
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        setValidationError(
          `File "${file.name}" (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds the maximum allowed size of 10 MB.`
        );
        return;
      }

      // Avoid duplicates in current selection
      if (!selectedFiles.some((f) => f.name === file.name && f.size === file.size)) {
        newFiles.push(file);
      }
    }

    if (newFiles.length > 0) {
      setSelectedFiles((prev) => [...prev, ...newFiles]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndAddFiles(e.dataTransfer.files);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndAddFiles(e.target.files);
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
    if (selectedFiles.length <= 1) {
      setValidationError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedFiles.length === 0) {
      setValidationError('Please select at least one document to upload.');
      return;
    }
    await onUpload(selectedFiles, docType);
    setSelectedFiles([]);
    setDocType('auto');
    setValidationError(null);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return <FileText className="w-5 h-5 text-red-500" />;
    if (ext === 'csv') return <FileSpreadsheet className="w-5 h-5 text-emerald-600" />;
    return <FileCode className="w-5 h-5 text-blue-500" />;
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-xl shadow-2xl border border-appBorder w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-appBorder bg-gray-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-100 flex items-center justify-center text-brand-600">
              <Upload className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-appText">
                Upload Procurement Documents
              </h3>
              <p className="text-xs text-appText-muted">
                PDF, TXT, or CSV files up to 10 MB each.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="text-appText-muted hover:text-appText p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Validation Alert */}
          {validationError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
              <span>{validationError}</span>
            </div>
          )}

          {/* Drag & Drop Box */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
              isDragOver
                ? 'border-brand-500 bg-brand-50/50'
                : 'border-gray-300 hover:border-brand-400 bg-gray-50/50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.txt,.csv"
              onChange={handleFileChange}
              className="hidden"
            />
            <div className="w-12 h-12 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center mx-auto mb-3">
              <Upload className="w-6 h-6" />
            </div>
            <p className="text-sm font-medium text-appText">
              Click to select or drag and drop files here
            </p>
            <p className="text-xs text-appText-muted mt-1">
              Supports PDF, TXT, and CSV (maximum 10 MB per file)
            </p>
          </div>

          {/* Document Type Selector */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Document Type (Optional)
            </label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="w-full text-sm px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-brand-500 focus:border-brand-500"
            >
              <option value="auto">Auto-detect from filename</option>
              <option value="purchase_order">Purchase Order (PO)</option>
              <option value="contract">Contract / Agreement</option>
              <option value="invoice">Invoice</option>
              <option value="procurement_note">Procurement Note</option>
              <option value="supplier_record">Supplier Record</option>
            </select>
            <span className="text-[11px] text-gray-500 mt-0.5 block">
              Auto-detect infers type based on keywords like "PO", "Contract", or "Note".
            </span>
          </div>

          {/* Selected Files List */}
          {selectedFiles.length > 0 && (
            <div>
              <div className="flex items-center justify-between text-xs font-semibold text-gray-700 mb-2">
                <span>Selected Files ({selectedFiles.length})</span>
                <button
                  type="button"
                  onClick={() => setSelectedFiles([])}
                  className="text-red-600 hover:text-red-700 font-normal hover:underline"
                >
                  Clear all
                </button>
              </div>
              <div className="max-h-36 overflow-y-auto space-y-1.5 border border-gray-200 rounded-lg p-2 bg-gray-50/50">
                {selectedFiles.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    className="flex items-center justify-between bg-white px-3 py-2 rounded border border-gray-200 text-xs"
                  >
                    <div className="flex items-center gap-2 truncate pr-2">
                      {getFileIcon(file.name)}
                      <span className="font-medium text-gray-800 truncate">
                        {file.name}
                      </span>
                      <span className="text-gray-400 text-[11px] shrink-0">
                        ({formatFileSize(file.size)})
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveFile(idx)}
                      disabled={isUploading}
                      className="text-gray-400 hover:text-red-600 p-1 transition-colors"
                      title="Remove file"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-appBorder">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onClose}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isUploading}
              disabled={selectedFiles.length === 0 || isUploading}
              icon={<CheckCircle2 className="w-3.5 h-3.5" />}
            >
              Upload & Extract ({selectedFiles.length})
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
