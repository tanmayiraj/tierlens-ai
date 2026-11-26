import apiClient from './apiClient';
import {
  DocumentListResponse,
  DocumentDetailResponse,
  DocumentEvidenceResponse,
  DocumentUploadResponse,
  LoadSamplesResponse,
  DocumentQueryParams,
} from '../types/document';

/**
 * List uploaded documents with optional filtering and pagination.
 * Conforms to API_SPEC.md Section 4.2 (GET /documents).
 */
export const getDocuments = async (
  params?: DocumentQueryParams
): Promise<DocumentListResponse> => {
  const query: Record<string, string | number> = {};

  if (params?.extraction_status && params.extraction_status !== 'all') {
    query.extraction_status = params.extraction_status;
  }
  if (params?.doc_type && params.doc_type !== 'all') {
    query.doc_type = params.doc_type;
  }
  if (params?.limit !== undefined) {
    query.limit = params.limit;
  }
  if (params?.offset !== undefined) {
    query.offset = params.offset;
  }

  const response = await apiClient.get<DocumentListResponse>('/documents', {
    params: query,
  });
  return response.data;
};

/**
 * Retrieves document details, metadata, and extraction statistics.
 * Conforms to API_SPEC.md Section 4.2 (GET /documents/{id}).
 */
export const getDocumentDetail = async (
  id: number
): Promise<DocumentDetailResponse> => {
  const response = await apiClient.get<DocumentDetailResponse>(`/documents/${id}`);
  return response.data;
};

/**
 * Retrieves verbatim evidence snippets extracted from a document.
 * Conforms to API_SPEC.md Section 4.2 (GET /documents/{id}/evidence).
 */
export const getDocumentEvidence = async (
  id: number
): Promise<DocumentEvidenceResponse> => {
  const response = await apiClient.get<DocumentEvidenceResponse>(
    `/documents/${id}/evidence`
  );
  return response.data;
};

/**
 * Uploads one or more procurement files (PDF, TXT, CSV up to 10 MB each).
 * Conforms to API_SPEC.md Section 4.2 (POST /documents/upload).
 */
export const uploadDocuments = async (
  files: File[],
  docType?: string
): Promise<DocumentUploadResponse> => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  if (docType && docType !== 'auto') {
    formData.append('doc_type', docType);
  }

  const response = await apiClient.post<DocumentUploadResponse>(
    '/documents/upload',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};

/**
 * Loads the bundled synthetic dataset and triggers document extraction.
 * Conforms to API_SPEC.md Section 4.2 (POST /documents/load-samples).
 */
export const loadSamples = async (): Promise<LoadSamplesResponse> => {
  const response = await apiClient.post<LoadSamplesResponse>(
    '/documents/load-samples'
  );
  return response.data;
};

export default {
  getDocuments,
  getDocumentDetail,
  getDocumentEvidence,
  uploadDocuments,
  loadSamples,
};
