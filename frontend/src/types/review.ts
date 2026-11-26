export interface ReviewQueueItem {
  relationship_id: number;
  supplier: string;
  buyer: string;
  material: string;
  confidence: number | null;
  snippet: string | null;
  document: string | null;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
}

export interface ReviewCorrections {
  share_pct?: number | null;
  lead_time_days?: number | null;
}

export interface ReviewRequest {
  action: 'approve' | 'reject';
  corrections?: ReviewCorrections;
  reviewed_by?: string;
}

export interface ReviewResponse {
  id: number;
  status: 'approved' | 'rejected';
  graph_rebuild_required: boolean;
}
