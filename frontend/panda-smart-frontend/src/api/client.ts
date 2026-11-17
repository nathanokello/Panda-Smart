import type { Advice, ApiErrorShape, Crop, CropCode, DashboardWardSummary, Farmer, Lot, Paginated, User, Ward, WardDashboard } from './types';
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';
const TOKEN_KEY = 'panda_smart_token';
export const auth = {
  token: () => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};
export class ApiError extends Error { status: number; code?: string; fields?: Record<string,string[]>; constructor(message:string,status=0,shape?:ApiErrorShape){super(message);this.status=status;this.code=shape?.error?.code;this.fields=shape?.error?.fields;} }
async function request<T>(path:string, init:RequestInit = {}, publicRequest=false):Promise<T>{
  const headers = new Headers(init.headers); headers.set('Accept','application/json');
  if(init.body && !(init.body instanceof URLSearchParams)) headers.set('Content-Type','application/json');
  const token=auth.token(); if(token && !publicRequest) headers.set('Authorization',`Token ${token}`);
  const res=await fetch(`${API_BASE}/api/v1${path}`,{...init,headers});
  if(!res.ok){let shape:ApiErrorShape={};try{shape=await res.json()}catch{};throw new ApiError(shape.error?.message || `Request failed (${res.status})`,res.status,shape);}
  const type=res.headers.get('content-type')||''; return (type.includes('application/json')?res.json():res.text()) as Promise<T>;
}
// DRF paginates list endpoints; reference-data screens need the plain rows.
function unwrap<T>(response: Paginated<T> | T[]): T[] {
  return Array.isArray(response) ? response : response.results;
}
const demoWard:Ward={id:'demo-ward-kitui-central',name:'Kitui Central',county:'Kitui'};
const demoCrops:Crop[]=[{code:'maize',name_en:'Maize',name_sw:'Mahindi',storable:true},{code:'green_gram',name_en:'Green gram',name_sw:'Ndengu',storable:true},{code:'cowpea',name_en:'Cowpea',name_sw:'Kunde',storable:true},{code:'watermelon',name_en:'Watermelon',name_sw:'Tikiti maji',storable:false}];
const demoFarmers:Farmer[]=[{id:'demo-farmer-1',name:'Amina Mwende',phone:'+254700000001',ward:demoWard,consent_given:true},{id:'demo-farmer-2',name:'Joseph Kioko',phone:'+254700000002',ward:demoWard,consent_given:true}];
const demoLots:Lot[]=[{id:'demo-lot-1',crop:'green_gram',status:'stored',initial_weight_kg:500,registered_at:new Date().toISOString(),farmer:demoFarmers[1],summary:{latest_weight_kg:492,loss_kg:8,loss_pct:1.6,latest_moisture_pct:12.5}}];
async function fallback<T>(real:()=>Promise<T>, demo:()=>T):Promise<T>{try{return await real()}catch(e){if(USE_MOCKS){console.info('[Panda Smart demo mode] Using sample data:',(e as Error).message);return demo()}throw e}}
export const api={
  login:(phone:string,password:string)=>fallback(()=>request<{token:string;user:User}>('/auth/login/',{method:'POST',body:JSON.stringify({phone,password})},true),()=>({token:'demo-token-not-for-production',user:{id:'demo-user',name:'Demo Cooperative Agent',role:'agent'} as User})),
  me:()=>fallback(()=>request<User>('/auth/me/'),()=>({id:'demo-user',name:'Demo Cooperative Agent',role:'agent'} as User)),
  wards:()=>fallback(async()=>unwrap(await request<Paginated<Ward>>('/wards/')),()=>[demoWard]),
  crops:()=>fallback(async()=>unwrap(await request<Paginated<Crop>>('/crops/')),()=>demoCrops),
  farmers:{list:()=>fallback(()=>request<{count:number;results:Farmer[]}>('/farmers/'),()=>({count:demoFarmers.length,results:demoFarmers})),register:(payload:Record<string,unknown>)=>request<Farmer>('/farmers/',{method:'POST',body:JSON.stringify(payload)})},
  lots:{list:()=>fallback(()=>request<{count:number;results:Lot[]}>('/lots/'),()=>({count:demoLots.length,results:demoLots})),create:(payload:Record<string,unknown>)=>request<Lot>('/lots/',{method:'POST',body:JSON.stringify(payload)})},
  advice:(ward:string,crop:CropCode)=>fallback(()=>request<Advice>(`/advice/?ward=${encodeURIComponent(ward)}&crop=${crop}`),()=>({ward:demoWard,crop,recommended_window:{start:'2026-11-25',end:'2026-12-05'},confidence:.7,rationale:'Demo guidance only. The backend rules service will provide the live recommendation.',rule_set_version:'demo-v1',alternatives:['cowpea']})),
  intents:{create:(payload:Record<string,unknown>)=>request<Record<string,unknown>>('/planting-intents/',{method:'POST',body:JSON.stringify(payload)})},
  dashboard:{
    wards:()=>fallback(()=>request<DashboardWardSummary[]>('/dashboard/wards/'),()=>[{id:demoWard.id,name:demoWard.name,county:demoWard.county||'',region:'',crop_count:1,total_intended_acres:24,stored_stock_kg:4200,generated_at:new Date().toISOString()}]),
    ward:(id:string)=>fallback(()=>request<WardDashboard>(`/dashboard/wards/${encodeURIComponent(id)}/`),()=>({ward:demoWard,generated_at:new Date().toISOString(),crops:[{crop:'green_gram' as CropCode,intended_acres:24,expected_demand_acres:20,oversubscription_pct:20,stored_stock_kg:4200,avg_loss_pct:1.6,latest_price_per_kg_kes:95,sell_flag:'watch' as const,sell_flag_reason:'Demo value only.',suppressed:false}]})),
  },
  verify:(token:string)=>request<Record<string,unknown>>(`/verify/${encodeURIComponent(token)}/`,{},true),
  confirm:(token:string)=>request<Record<string,unknown>>(`/verify/${encodeURIComponent(token)}/confirm/`,{method:'POST'},true),
  dispute:(token:string,reason:string)=>request<Record<string,unknown>>(`/verify/${encodeURIComponent(token)}/dispute/`,{method:'POST',body:JSON.stringify({reason})},true),
};
