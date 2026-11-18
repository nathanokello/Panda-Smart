import type { Advice, ApiErrorShape, Crop, CropCode, DashboardWardSummary, Farmer, Lot, MyDashboard, Paginated, Plot, ProduceListing, SeasonRecord, User, Ward, WardDashboard } from './types';
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
  if(res.status===401 && token && !publicRequest){auth.clear();window.dispatchEvent(new Event('panda:unauthorized'))}
  if(!res.ok){let shape:ApiErrorShape={};try{shape=await res.json()}catch{};throw new ApiError(shape.error?.message || `Request failed (${res.status})`,res.status,shape);}
  const type=res.headers.get('content-type')||''; return (type.includes('application/json')?res.json():res.text()) as Promise<T>;
}
// DRF paginates list endpoints (20 rows by default). Follow "next" so dropdowns
// see every ward, farmer and lot, not just the first page.
async function listAll<T>(path:string, publicRequest=false):Promise<T[]>{
  const rows:T[]=[]; let next:string|null=`${path}${path.includes('?')?'&':'?'}limit=100`; let guard=0;
  while(next && guard<50){
    const page:Paginated<T>|T[]=await request<Paginated<T>|T[]>(next,{},publicRequest);
    if(Array.isArray(page)) return page;
    rows.push(...page.results);
    // "next" is an absolute URL on the API origin; keep only the path after /api/v1.
    next=page.next?(()=>{const u:URL=new URL(page.next as string);return u.pathname.replace(/^.*\/api\/v1/,'')+u.search})():null;
    guard+=1;
  }
  return rows;
}
const asPage=<T,>(rows:T[])=>({count:rows.length,results:rows});
const demoWard:Ward={id:'demo-ward-kitui-central',name:'Kitui Central',county:'Kitui'};
const demoCrops:Crop[]=[{code:'maize',name_en:'Maize',name_sw:'Mahindi',storable:true},{code:'green_gram',name_en:'Green gram',name_sw:'Ndengu',storable:true},{code:'cowpea',name_en:'Cowpea',name_sw:'Kunde',storable:true},{code:'watermelon',name_en:'Watermelon',name_sw:'Tikiti maji',storable:false}];
const demoFarmers:Farmer[]=[{id:'demo-farmer-1',name:'Amina Mwende',phone:'+254700000001',ward:demoWard,consent_given:true},{id:'demo-farmer-2',name:'Joseph Kioko',phone:'+254700000002',ward:demoWard,consent_given:true}];
const demoLots:Lot[]=[{id:'demo-lot-1',crop:'green_gram',status:'stored',initial_weight_kg:500,registered_at:new Date().toISOString(),farmer:demoFarmers[1],summary:{latest_weight_kg:492,loss_kg:8,loss_pct:1.6,latest_moisture_pct:12.5}}];
async function fallback<T>(real:()=>Promise<T>, demo:()=>T):Promise<T>{try{return await real()}catch(e){if(USE_MOCKS){console.info('[Panda Smart demo mode] Using sample data:',(e as Error).message);return demo()}throw e}}
export const api={
  login:(phone:string,password:string)=>fallback(()=>request<{token:string;user:User}>('/auth/login/',{method:'POST',body:JSON.stringify({phone,password})},true),()=>({token:'demo-token-not-for-production',user:{id:'demo-user',name:'Demo Cooperative Agent',role:'agent'} as User})),
  logout:async()=>{try{await request<unknown>('/auth/logout/',{method:'POST'})}catch{/* still sign out locally */}auth.clear()},
  me:()=>fallback(()=>request<User>('/auth/me/'),()=>({id:'demo-user',name:'Demo Cooperative Agent',role:'agent'} as User)),
  wards:()=>fallback(()=>listAll<Ward>('/wards/',true),()=>[demoWard]),
  crops:()=>fallback(()=>listAll<Crop>('/crops/',true),()=>demoCrops),
  farmers:{list:()=>fallback(async()=>asPage(await listAll<Farmer>('/farmers/')),()=>({count:demoFarmers.length,results:demoFarmers})),register:(payload:Record<string,unknown>)=>request<Farmer>('/farmers/',{method:'POST',body:JSON.stringify(payload)})},
  lots:{list:()=>fallback(async()=>asPage(await listAll<Lot>('/lots/')),()=>({count:demoLots.length,results:demoLots})),create:(payload:Record<string,unknown>)=>request<Lot>('/lots/',{method:'POST',body:JSON.stringify(payload)})},
  advice:(ward:string,crop:CropCode)=>fallback(()=>request<Advice>(`/advice/?ward=${encodeURIComponent(ward)}&crop=${crop}`),()=>({ward:demoWard,crop,recommended_window:{start:'2026-11-25',end:'2026-12-05'},confidence:.7,rationale:'Demo guidance only. The backend rules service will provide the live recommendation.',rule_set_version:'demo-v1',alternatives:['cowpea']})),
  intents:{create:(payload:Record<string,unknown>)=>request<Record<string,unknown>>('/planting-intents/',{method:'POST',body:JSON.stringify(payload)})},
  dashboard:{
    wards:()=>fallback(()=>request<DashboardWardSummary[]>('/dashboard/wards/'),()=>[{id:demoWard.id,name:demoWard.name,county:demoWard.county||'',region:'',crop_count:1,total_intended_acres:24,stored_stock_kg:4200,generated_at:new Date().toISOString()}]),
    ward:(id:string)=>fallback(()=>request<WardDashboard>(`/dashboard/wards/${encodeURIComponent(id)}/`),()=>({ward:demoWard,generated_at:new Date().toISOString(),crops:[{crop:'green_gram' as CropCode,intended_acres:24,expected_demand_acres:20,oversubscription_pct:20,stored_stock_kg:4200,avg_loss_pct:1.6,latest_price_per_kg_kes:95,sell_flag:'watch' as const,sell_flag_reason:'Demo value only.',suppressed:false}]})),
    me:()=>fallback(()=>request<MyDashboard>('/dashboard/me/'),()=>({farmer:{id:'demo-farmer-1',name:'Demo Farmer',ward:demoWard.name},stats:{farms:2,total_acres:12.5,active_crops:3,active_crop_codes:['maize','green_gram'] as CropCode[],stored_produce_kg:8200,stored_produce_tonnes:8.2},primary_farm:{id:'demo-plot-1',ward:demoWard.name,acres:2.5,crop:'Maize'},ai_recommendation:{ward:demoWard,crop:'maize' as CropCode,recommended_window:{start:'2026-11-20',end:'2026-12-10'},confidence:.92,rationale:'Demo guidance only.',rule_set_version:'demo-v1',alternatives:[]},weather:{enabled:true,ward:demoWard.name,days:[{date:new Date().toISOString().slice(0,10),rain_mm:4,temp_max_c:24,temp_min_c:16,rain_chance_pct:20}]},recent_activity:[{type:'lot_event',label:'Lot registered',detail:'1,000 kg of maize',at:new Date().toISOString()}],season:'2026-short-rains'})),
  },
  plots:{list:(farmerId:string)=>fallback(async()=>asPage(await listAll<Plot>(`/farmers/${encodeURIComponent(farmerId)}/plots/`)),()=>({count:0,results:[]})),create:(farmerId:string,payload:Record<string,unknown>)=>request<Plot>(`/farmers/${encodeURIComponent(farmerId)}/plots/`,{method:'POST',body:JSON.stringify(payload)})},
  seasons:{list:(farmerId:string)=>fallback(()=>request<SeasonRecord[]|{results:SeasonRecord[]}>(`/farmers/${encodeURIComponent(farmerId)}/seasons/`),()=>[])},
  history:(farmerId:string)=>fallback(()=>request<Record<string,unknown>>(`/farmers/${encodeURIComponent(farmerId)}/history/`),()=>({})),
  myVerificationLinks:()=>fallback(()=>request<{links:string[]}>('/me/verification-links/'),()=>({links:[]})),
  marketplace:{
    list:(crop?:string)=>fallback(()=>listAll<ProduceListing>(`/marketplace/${crop?`?crop=${encodeURIComponent(crop)}`:''}`,true),()=>[]),
    create:(payload:Record<string,unknown>)=>request<ProduceListing>('/marketplace/',{method:'POST',body:JSON.stringify(payload)}),
  },
  verify:(token:string)=>request<Record<string,unknown>>(`/verify/${encodeURIComponent(token)}/`,{},true),
  confirm:(token:string)=>request<Record<string,unknown>>(`/verify/${encodeURIComponent(token)}/confirm/`,{method:'POST'},true),
  dispute:(token:string,reason:string)=>request<Record<string,unknown>>(`/verify/${encodeURIComponent(token)}/dispute/`,{method:'POST',body:JSON.stringify({reason})},true),
};
