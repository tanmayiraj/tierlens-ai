export type ExtractionStatus = 'pending' | 'processing' | 'done' | 'failed';

export type DocType =
  | 'purchase_order'
  | 'supplier_record'
  | 'contract'
  | 'invoice'
  | 'procurement_note';

export interface DocumentUploadItem {
  id: number;
  filename: string;
  extraction_status: ExtractionStatus;
}

export interface DocumentUploadResponse {
  documents: DocumentUploadItem[];
}

export interface LoadSamplesResponse {
  loaded: number;
  queued_for_extraction: number;
}

export interface DocumentListItem {
  id: number;
  filename: string;
  doc_type: string;
  extraction_status: ExtractionStatus;
  uploaded_at: string;
  relationships_found: number;
}

export interface DocumentListResponse {
  items: DocumentListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentStats {
  entities: number;
  relationships: number;
  low_confidence: number;
}

export interface DocumentDetailResponse {
  id: number;
  filename: string;
  doc_type: string;
  page_count: number | null;
  extraction_status: ExtractionStatus;
  uploaded_at: string;
  stats: DocumentStats;
}

export interface DocumentEvidenceRelationshipRef {
  id: number;
  supplier: string;
  buyer: string;
  material: string;
}

export interface DocumentEvidenceItem {
  id: number;
  page: number | null;
  snippet: string;
  llm_confidence: number | null;
  relationship: DocumentEvidenceRelationshipRef | null;
}

export interface DocumentEvidenceResponse {
  document_id: number;
  evidence: DocumentEvidenceItem[];
}

export interface DocumentQueryParams {
  extraction_status?: string;
  doc_type?: string;
  limit?: number;
  offset?: number;
}
