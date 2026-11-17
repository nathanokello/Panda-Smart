export type Role = 'farmer' | 'agent' | 'coop_admin' | 'admin';
export type CropCode = 'maize' | 'green_gram' | 'cowpea' | 'watermelon';
export interface User { id: string; name: string; role: Role; tenant_id?: string }
export interface Ward { id: string; name: string; county?: string }
export interface Crop { code: CropCode; name_en: string; name_sw: string; storable: boolean }
export interface Farmer { id: string; name: string; phone: string; ward: Ward | string; consent_given?: boolean; tenant_id?: string }
export interface Lot { id: string; crop: CropCode; status: string; initial_weight_kg: number; registered_at: string; farmer?: Farmer; summary?: {latest_weight_kg:number; loss_kg:number; loss_pct:number; latest_moisture_pct?:number|null} }
export interface Advice { ward: Ward; crop: CropCode; recommended_window: {start:string;end:string}; confidence:number; rationale:string; rule_set_version:string; alternatives:string[] }
export interface ApiErrorShape { error?: { code?: string; message?: string; fields?: Record<string,string[]> } }

// Django REST Framework paginates list endpoints with LimitOffsetPagination.
export interface Paginated<T> { count: number; next: string | null; previous: string | null; results: T[] }

// GET /dashboard/wards/ -> ward summary rows (architecture.md 6.4).
export interface DashboardWardSummary {
  id: string; name: string; county: string; region: string;
  crop_count: number; total_intended_acres: number; stored_stock_kg: number;
  generated_at: string;
}

// GET /dashboard/wards/{id}/ -> per-crop detail (architecture.md 6.4).
export interface DashboardCrop {
  crop: CropCode;
  intended_acres: number | null;
  expected_demand_acres: number | null;
  oversubscription_pct: number | null;
  stored_stock_kg: number | null;
  avg_loss_pct: number | null;
  latest_price_per_kg_kes: number | null;
  sell_flag: 'sell_now' | 'hold' | 'watch' | null;
  sell_flag_reason: string;
  suppressed: boolean;
}
export interface WardDashboard { ward: Ward; generated_at: string; crops: DashboardCrop[] }
