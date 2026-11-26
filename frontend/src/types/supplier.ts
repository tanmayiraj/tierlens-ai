export interface SupplierListItem {
  id: number;
  name: string;
  country: string | null;
  region: string | null;
  tier: number | null;
  risk_score: number | null;
  materials: string[];
}

export interface SupplierListResponse {
  items: SupplierListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface SupplierDetailSupplied {
  id: number;
  name: string;
  material: string;
}

export interface SupplierDetailMaterial {
  id: number;
  name: string;
  qualified: boolean;
}

export interface SupplierDetailResponse {
  id: number;
  name: string;
  aliases: string[];
  country: string | null;
  region: string | null;
  capacity_per_month: number | null;
  base_risk: number;
  tier: number | null;
  supplies_to: SupplierDetailSupplied[];
  supplied_by: SupplierDetailSupplied[];
  materials: SupplierDetailMaterial[];
}

export interface SupplierFilters {
  q?: string;
  region?: string;
  tier?: number;
  min_risk?: number;
  limit?: number;
  offset?: number;
}
