import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { BrowserRouter, NavLink, Route, Routes, useNavigate, useParams } from 'react-router-dom';
import { api, auth, ApiError } from './api/client';
import type { Advice, Crop, CropCode, DashboardCrop, Farmer, Lot, MyDashboard, Plot, ProduceListing, SeasonRecord, User, Ward } from './api/types';
import './index.css';

const ICONS:Record<string,string>={dashboard:'🏠',farms:'🌱',advice:'💡',crops:'🌾',lots:'📦',market:'🛒',analytics:'📊',storage:'🏬',verify:'✅',profile:'👤',settings:'⚙️',farmers:'👥',intents:'🗓️',ward:'📍'}
function Icon({name}:{name:string}){return <span className="navicon" aria-hidden="true">{ICONS[name]||'•'}</span>}
function Shell({user,onLogout}:{user:User;onLogout:()=>void}){
 const [menu,setMenu]=useState(false);
 const isFarmer=user.role==='farmer';
 const isStaff=user.role==='agent'||user.role==='coop_admin'||user.role==='admin';
 const nav:[string,string,string][]=[['/','Dashboard','dashboard'],
  ...(isFarmer?[['/farms','My Farms','farms'],['/advice','Planting Advice','advice'],['/intents','Planting slots','intents'],['/crops','My Crops','crops'],['/lots','Hifadhi Mavuno','lots'],['/market','Marketplace','market'],['/analytics','Crop Analytics','analytics'],['/verification','Verification','verify']] as [string,string,string][]:[]),
  ...(isStaff?[['/advice','Planting Advice','advice'],['/intents','Planting slots','intents'],['/lots','Hifadhi Mavuno','lots'],['/farmers','Farmers','farmers']] as [string,string,string][]:[]),
  ...(user.role==='coop_admin'||user.role==='admin'?[['/ward-dashboard','Ward dashboard','ward']] as [string,string,string][]:[]),
  ['/profile','Profile','profile'],['/settings','Settings','settings']];
 return <div className="shell"><aside className={menu?'sidebar open':'sidebar'}><div className="brand"><img src="/panda-smart-logo.png"/><span>Panda Smart</span></div><div className="navlabel">WORKSPACE</div><nav>{nav.map(([to,label,icon])=><NavLink key={to+label} to={to} end={to==='/'} onClick={()=>setMenu(false)}><Icon name={icon}/>{label}</NavLink>)}</nav><div className="sidebottom"><div className="avatar">{user.name.slice(0,1).toUpperCase()}</div><div><b>{user.name}</b><small>{user.role.replace('_',' ')}</small></div><button className="link" onClick={onLogout}>Log out</button></div></aside><main className="main"><header><button className="hamb" onClick={()=>setMenu(!menu)}>☰</button><div className="searchbox"><span>🔍</span><input placeholder="Search for crops, advice, or features…" disabled title="Search is on the roadmap"/></div><button className="bell" title="Notifications" aria-label="Notifications">🔔{user.role==='farmer'?<span className="dot"/>:null}</button><div className="who"><div className="avatar small">{user.name.slice(0,1).toUpperCase()}</div><div><b>{user.name}</b><small>{user.role.replace('_',' ')}</small></div></div></header><section className="content"><Routes><Route path="/" element={<Dashboard user={user}/>}/><Route path="/advice" element={<AdvicePage/>}/><Route path="/intents" element={<IntentPage user={user}/>}/><Route path="/lots" element={<LotsPage/>}/><Route path="/farmers" element={<FarmersPage/>}/><Route path="/farms" element={<MyFarmsPage user={user}/>}/><Route path="/crops" element={<MyCropsPage user={user}/>}/><Route path="/analytics" element={<CropAnalyticsPage user={user}/>}/><Route path="/market" element={<MarketplacePage user={user}/>}/><Route path="/storage" element={<StoragePage/>}/> <Route path="/verification" element={<VerificationPage/>}/><Route path="/profile" element={<ProfilePage user={user}/>}/><Route path="/settings" element={<SettingsPage/>}/><Route path="/ward-dashboard" element={<WardDashboard/>}/><Route path="*" element={<Dashboard user={user}/>}/></Routes></section></main></div>
}
function Panel({title,children}:{title:string;children:ReactNode}){return <div className="panel"><h3>{title}</h3>{children}</div>}
function Notice({children}:{children:ReactNode}){return <p className="notice">{children}</p>}
function Overview(){return <><div className="welcome"><div><span className="eyebrow">PANDA SMART · AGRICULTURAL INTELLIGENCE</span><h1>Plan better. Store safely. Sell smarter.</h1><p>One connected view of planting decisions and harvest records.</p></div><div className="welcome-leaf">🌱</div></div><div className="stats"><Stat label="Planting advice" value="Ward-based" note="Rules-powered recommendations"/><Stat label="Storage records" value="Traceable" note="Append-only lot history"/><Stat label="Verification" value="Farmer-led" note="Private verification links"/><Stat label="Market signals" value="Ward level" note="Planning and sell-timing flags"/></div><div className="twocol"><Panel title="Your workflow"><div className="steps"><p><b>01 · Plan</b><span>Choose a ward and crop to view the recommended planting window.</span></p><p><b>02 · Coordinate</b><span>Register intended acreage and check slot availability.</span></p><p><b>03 · Store</b><span>Agents register grain lots and record moisture and check-ups.</span></p><p><b>04 · Verify & sell</b><span>Farmers confirm records; cooperatives monitor ward stock and sell-timing signals.</span></p></div></Panel><Panel title="Prototype status"><Notice>This interface follows the backend architecture contract. Sample values are clearly marked when demo mode is enabled.</Notice><p className="muted">The live system uses Django REST Framework, PostgreSQL and token authentication. No Supabase connection is required by this backend contract.</p></Panel></div></>}
function Stat({label,value,note,tone,icon}:{label:string;value:string;note:string;tone?:string;icon?:string}){return <div className={tone?`stat tone-${tone}`:'stat'}>{icon&&<span className="staticon">{icon}</span>}<small>{label}</small><strong>{value}</strong><span>{note}</span></div>}
function timeAgo(iso:string):string{const d=(Date.now()-new Date(iso).getTime())/1000;if(d<60)return 'just now';if(d<3600)return `${Math.floor(d/60)} min ago`;if(d<86400)return `${Math.floor(d/3600)} hours ago`;return `${Math.floor(d/86400)} day${Math.floor(d/86400)===1?'':'s'} ago`}
const CROP_LABELS:Record<string,string>={maize:'Maize',green_gram:'Green gram',cowpea:'Cowpea',watermelon:'Watermelon'}
function Dashboard({user}:{user:User}){return user.role==='farmer'?<FarmerDashboard user={user}/>:<Overview/>}
function FarmerDashboard({user}:{user:User}){
 const [data,setData]=useState<MyDashboard|null>(null),[error,setError]=useState('');
 useEffect(()=>{api.dashboard.me().then(setData).catch(e=>setError((e as Error).message))},[]);
 const firstName=user.name.split(' ')[0];
 if(error)return <Notice>{error}</Notice>;
 if(!data)return <p className="muted">Loading your dashboard…</p>;
 const rec=data.ai_recommendation;
 return <>
  <div className="welcome"><div><span className="eyebrow">PANDA SMART · AGRICULTURAL INTELLIGENCE</span><h1>Welcome back, {firstName}! 👋</h1><p>Smart farming. Greater harvests.</p></div><div className="welcome-leaf">🌾</div></div>
  <div className="stats">
   <Stat tone="green" icon="🌱" label="My Farms" value={String(data.stats.farms)} note="Registered plots"/>
   <Stat tone="blue" icon="🌾" label="Total Land" value={`${data.stats.total_acres} Acres`} note="Across all farms"/>
   <Stat tone="yellow" icon="🌽" label="Active Crops" value={String(data.stats.active_crops)} note={data.stats.active_crop_codes.map(c=>CROP_LABELS[c]||c).join(', ')||'None this season'}/>
   <Stat tone="purple" icon="🏭" label="Stored Produce" value={`${data.stats.stored_produce_tonnes} Tonnes`} note="In Hifadhi Mavuno"/>
  </div>
  <div className="twocol">
   <Panel title={`Weather Forecast – ${data.weather.ward||data.farmer.ward}`}>
    {data.weather.enabled?(data.weather.days&&data.weather.days.length?<div className="weather-row"><div className="weather-temp">{Math.round(data.weather.days[0].temp_max_c??0)}°C<small>{data.weather.days[0].rain_chance_pct!=null?'Chance of rain':'Forecast'}</small></div><div className="weather-meta"><span>Rain chance<b>{data.weather.days[0].rain_chance_pct??'—'}%</b></span><span>Low<b>{data.weather.days[0].temp_min_c??'—'}°C</b></span></div></div>:<Notice>{data.weather.message||'No forecast available for this ward yet.'}</Notice>):<Notice>Live weather forecasts are turned off in this environment (OPEN_METEO_ENABLED=0 in the backend .env). Turn it on to show real forecasts here.</Notice>}
   </Panel>
   <Panel title="Planting recommendation (rule-based)">
    {rec?<><div className="advice-result"><div><small>{CROP_LABELS[rec.crop]||rec.crop} · {Math.round(rec.confidence*100)}% confidence</small><h2>{rec.recommended_window.start} – {rec.recommended_window.end}</h2><p className="muted">{rec.rationale}</p></div></div><NavLink to="/advice" className="primary" style={{display:'inline-block',textDecoration:'none',textAlign:'center'}}>Get full advice →</NavLink></>:<Notice>Register a planting intent to get a tailored recommendation.</Notice>}
   </Panel>
  </div>
  <div className="twocol three">
   <Panel title="Your Farm Overview">
    {data.primary_farm?<div className="farmoverview"><div><b>{data.primary_farm.ward} Farm</b><span>{data.primary_farm.acres} Acres{data.primary_farm.crop?` · ${data.primary_farm.crop}`:''}</span></div><NavLink to="/farms" className="secondary" style={{textDecoration:'none'}}>View Farm →</NavLink></div>:<Notice>No farms registered yet. <NavLink to="/farms">Add your first farm</NavLink>.</Notice>}
   </Panel>
   <Panel title="Recent Activity">
    {data.recent_activity.length?<div className="activity">{data.recent_activity.map((a,i)=><div key={i} className="activity-row"><div><b>{a.label}</b><span>{a.detail}</span></div><small>{timeAgo(a.at)}</small></div>)}</div>:<p className="muted">No activity recorded yet.</p>}
   </Panel>
   <Panel title="Together for a Food Secure Kenya"><p className="muted">Panda Smart — empowering farmers, enriching lives.</p></Panel>
  </div>
 </>
}
function MyFarmsPage({user}:{user:User}){
 const [plots,setPlots]=useState<Plot[]>([]),[wards,setWards]=useState<Ward[]>([]),[ward,setWard]=useState(''),[acres,setAcres]=useState('1'),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const farmerId=user.farmer_id||'';
 function load(){if(farmerId)api.plots.list(farmerId).then(r=>setPlots('results' in r?r.results:r as any)).catch(e=>setError((e as Error).message))}
 useEffect(()=>{load();api.wards().then(x=>{setWards(x);if(x[0])setWard(x[0].id)})},[farmerId]);
 async function submit(e:FormEvent){e.preventDefault();if(!farmerId)return;setBusy(true);setError('');try{await api.plots.create(farmerId,{ward,acres:Number(acres)});load()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <><PageTitle title="My Farms" desc="Plots you have registered, and their size and ward."/>
  {!farmerId&&<Notice>Your account has no linked farmer profile, so farms cannot be shown.</Notice>}
  <Panel title="Register a new farm"><form onSubmit={submit} className="formgrid"><label>Ward<select value={ward} onChange={e=>setWard(e.target.value)}>{wards.map(w=><option key={w.id} value={w.id}>{w.name}{w.county?`, ${w.county}`:''}</option>)}</select></label><label>Area (acres)<input type="number" min=".1" step=".1" value={acres} onChange={e=>setAcres(e.target.value)}/></label><button className="primary" disabled={busy||!farmerId}>{busy?'Saving…':'Add farm'}</button></form></Panel>
  {error&&<Notice>{error}</Notice>}
  <div className="cardgrid">{plots.map(p=><div key={p.id} className="farmcard"><b>{p.acres} Acres</b><span>Registered {new Date(p.created_at).toLocaleDateString()}</span></div>)}{!plots.length&&<p className="muted">No farms registered yet.</p>}</div>
 </>}
function MyCropsPage({user}:{user:User}){
 const [records,setRecords]=useState<SeasonRecord[]>([]),[error,setError]=useState('');
 const farmerId=user.farmer_id||'';
 useEffect(()=>{if(farmerId)api.seasons.list(farmerId).then(r=>setRecords(Array.isArray(r)?r:r.results)).catch(e=>setError((e as Error).message))},[farmerId]);
 return <><PageTitle title="My Crops" desc="What you have planted this season and in past seasons."/>{error&&<Notice>{error}</Notice>}
  <div className="tablewrap"><table><thead><tr><th>Season</th><th>Crop</th><th>Acres</th><th>Planted</th><th>Harvested</th><th>Harvest (kg)</th></tr></thead><tbody>{records.map(r=><tr key={r.id}><td>{r.season}</td><td>{CROP_LABELS[r.crop]||r.crop}</td><td>{r.acres??'—'}</td><td>{r.planted_on||'—'}</td><td>{r.harvested_on||'Not yet'}</td><td>{r.harvest_kg??'—'}</td></tr>)}</tbody></table></div>
  {!records.length&&!error&&<p className="muted">No season records yet. These are usually added by your cooperative agent or extension officer.</p>}
 </>}
function CropAnalyticsPage({user}:{user:User}){
 const [data,setData]=useState<any>(null),[error,setError]=useState('');
 const farmerId=user.farmer_id||'';
 useEffect(()=>{if(farmerId)api.history(farmerId).then(setData).catch(e=>setError((e as Error).message))},[farmerId]);
 return <><PageTitle title="Crop Analytics" desc="Yield per acre and storage loss, by crop, from your own records."/>{error&&<Notice>{error}</Notice>}
  {data&&<div className="tablewrap"><table><thead><tr><th>Crop</th><th>Seasons</th><th>Avg yield (kg/acre)</th><th>Storage lots</th><th>Avg storage loss</th></tr></thead><tbody>{(data.crops||[]).map((c:any)=><tr key={c.crop}><td>{CROP_LABELS[c.crop]||c.crop}</td><td>{c.seasons}</td><td>{c.avg_yield_kg_per_acre??'—'}</td><td>{c.storage_lots}</td><td>{c.avg_storage_loss_pct!=null?`${c.avg_storage_loss_pct}%`:'—'}</td></tr>)}</tbody></table></div>}
  {data&&data.latest_soil_test&&<Panel title="Latest soil test"><p className="muted">Tested {data.latest_soil_test.tested_on}</p><ul>{data.latest_soil_test.guidance.map((g:string,i:number)=><li key={i}>{g}</li>)}</ul></Panel>}
 </>}
function MarketplacePage({user}:{user:User}) {
 const [listings,setListings]=useState<ProduceListing[]>([]);
 const [crops,setCrops]=useState<Crop[]>([]);
 const [lots,setLots]=useState<Lot[]>([]);
 const [crop,setCrop]=useState<CropCode>('maize');
 const [lot,setLot]=useState('');
 const [quantity,setQuantity]=useState('500');
 const [price,setPrice]=useState('80');
 const [description,setDescription]=useState('');
 const [error,setError]=useState('');
 const [success,setSuccess]=useState('');
 function load(){api.marketplace.list().then(setListings).catch(e=>setError((e as Error).message))}
 useEffect(()=>{load();api.crops().then(setCrops).catch(()=>{});if(user.role==='farmer')api.lots.list().then(r=>setLots(r.results)).catch(()=>{})},[user.role]);
 async function publish(e:FormEvent){e.preventDefault();setError('');setSuccess('');try{await api.marketplace.create({crop,lot_id:lot||null,quantity_kg:Number(quantity),price_per_kg_kes:Number(price),description});setSuccess('Your produce listing is now live.');setDescription('');load()}catch(e){setError((e as Error).message)}}
 return <><PageTitle title="Agricultural Marketplace" desc="List stored produce or browse available produce from farmers."/>
  {error&&<Notice>{error}</Notice>}
  {success&&<Notice>{success}</Notice>}
  {user.role==='farmer'&&<Panel title="List your produce"><form onSubmit={publish} className="formgrid">
   <label>Crop<select value={crop} onChange={e=>setCrop(e.target.value as CropCode)}>{(crops.length?crops:[{code:'maize',name_en:'Maize'} as Crop]).filter(c=>c.storable).map(c=><option key={c.code} value={c.code}>{c.name_en}</option>)}</select></label>
   <label>Hifadhi Mavuno lot<select value={lot} onChange={e=>setLot(e.target.value)}><option value="">No lot selected</option>{lots.map(l=><option key={l.id} value={l.id}>{CROP_LABELS[l.crop]||l.crop} · {l.initial_weight_kg} kg</option>)}</select></label>
   <label>Quantity (kg)<input type="number" min=".01" step=".01" required value={quantity} onChange={e=>setQuantity(e.target.value)}/></label>
   <label>Expected price (KES/kg)<input type="number" min="0" step=".01" required value={price} onChange={e=>setPrice(e.target.value)}/></label>
   <label className="full">Description<textarea value={description} onChange={e=>setDescription(e.target.value)} placeholder="Quality, harvest date, delivery options…"/></label>
   <button className="primary">Publish listing</button>
  </form></Panel>}
  <div className="tablewrap"><table><thead><tr><th>Crop</th><th>Seller</th><th>Quantity</th><th>Price</th><th>Ward</th><th>Status</th></tr></thead><tbody>{listings.map(l=><tr key={l.id}><td>{CROP_LABELS[l.crop]||l.crop}</td><td>{l.farmer_name}</td><td>{l.quantity_kg} kg</td><td>KES {l.price_per_kg_kes}/kg</td><td>{l.ward}, {l.county}</td><td><span className="pill">Available</span></td></tr>)}</tbody></table></div>
  {!listings.length&&<p className="muted">No produce listings are available yet.</p>}
 </>}
function StoragePage(){return <><PageTitle title="Storage" desc="An overview of where your produce is stored."/><Notice>Storage is managed by your cooperative's agents through Hifadhi Mavuno. A self-service view for farmers is on our roadmap — for now, ask your agent for your lot status, or check Verification for links sent to your phone.</Notice></>}
function VerificationPage(){
 const [links,setLinks]=useState<string[]>([]),[error,setError]=useState('');
 useEffect(()=>{api.myVerificationLinks().then(r=>setLinks(r.links)).catch(e=>setError((e as Error).message))},[]);
 return <><PageTitle title="Verification" desc="Confirm or dispute produce records your cooperative has registered for you."/>{error&&<Notice>{error}</Notice>}
  {links.length?<div className="cardgrid">{links.map((l,i)=><a key={i} href={l} className="farmcard" style={{textDecoration:'none'}}><b>Verification link #{i+1}</b><span>Tap to open and confirm or dispute</span></a>)}</div>:<p className="muted">No pending verification links right now. You'll get an SMS/USSD link whenever a lot is registered in your name.</p>}
 </>}
function ProfilePage({user}:{user:User}){return <><PageTitle title="Profile" desc="Your account details."/><Panel title="Account"><div className="formgrid"><label>Name<input value={user.name} disabled/></label><label>Role<input value={user.role.replace('_',' ')} disabled/></label></div><p className="muted">Profile editing is on our roadmap. Contact your cooperative admin to update your details.</p></Panel></>}
function SettingsPage(){return <><PageTitle title="Settings" desc="Preferences for your account."/><Notice>Settings (notifications, language, SMS preferences) are on our roadmap.</Notice></>}
function AdvicePage(){const [wards,setWards]=useState<Ward[]>([]),[crops,setCrops]=useState<Crop[]>([]),[ward,setWard]=useState(''),[crop,setCrop]=useState<CropCode>('green_gram'),[result,setResult]=useState<Advice|null>(null),[error,setError]=useState('');useEffect(()=>{api.wards().then(x=>{setWards(x);if(x[0])setWard(x[0].id)}).catch(e=>setError((e as Error).message));api.crops().then(setCrops).catch(()=>{})},[]);async function submit(e:FormEvent){e.preventDefault();setError('');try{setResult(await api.advice(ward,crop))}catch(x){setError((x as Error).message)}}return <><PageTitle title="Planting advice" desc="Get a recommended planting window for a crop in your ward."/><Panel title="Find planting advice"><form onSubmit={submit} className="formgrid"><label>Ward<select value={ward} onChange={e=>setWard(e.target.value)}>{wards.map(w=><option key={w.id} value={w.id}>{w.name}{w.county?`, ${w.county}`:''}</option>)}</select></label><label>Crop<select value={crop} onChange={e=>setCrop(e.target.value as CropCode)}>{crops.map(c=><option key={c.code} value={c.code}>{c.name_en}</option>)}</select></label><button className="primary">Get recommendation</button></form></Panel>{error&&<Notice>{error}</Notice>}{result&&<Panel title="Recommended planting window"><div className="advice-result"><div><small>PLANTING WINDOW</small><h2>{result.recommended_window.start} – {result.recommended_window.end}</h2><p>{result.rationale}</p></div><div className="confidence">{Math.round(result.confidence*100)}%<small>confidence</small></div></div><p className="muted">Rule set: {result.rule_set_version} · Alternatives: {result.alternatives.join(', ')||'None listed'}</p></Panel>}</>}
function IntentPage({user}:{user:User}){
 const isFarmer=user.role==='farmer';
 const [farmers,setFarmers]=useState<Farmer[]>([]),[farmer,setFarmer]=useState(isFarmer?(user.farmer_id||''):''),[plots,setPlots]=useState<Plot[]>([]),[plot,setPlot]=useState(''),[crops,setCrops]=useState<Crop[]>([]),[crop,setCrop]=useState<CropCode>('green_gram'),[acres,setAcres]=useState('1'),[season,setSeason]=useState('2026-short-rains'),[result,setResult]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{api.crops().then(setCrops).catch(()=>{});if(!isFarmer)api.farmers.list().then(r=>{const ok=r.results.filter(f=>f.consent_given);setFarmers(ok);if(ok[0])setFarmer(ok[0].id)}).catch(e=>setError((e as Error).message))},[isFarmer]);
 useEffect(()=>{setPlot('');if(farmer)api.plots.list(farmer).then(r=>setPlots(r.results)).catch(()=>setPlots([]));else setPlots([])},[farmer]);
 async function submit(e:FormEvent){e.preventDefault();if(!farmer)return;setBusy(true);setError('');setResult(null);try{setResult(await api.intents.create({farmer_id:farmer,plot_id:plot||null,crop,acres:Number(acres),season:season.trim()||undefined}))}catch(x){setError((x as Error).message)}finally{setBusy(false)}}
 return <><PageTitle title="Planting slots" desc="Tell your ward what you plan to plant. If too many farmers choose the same crop, you are moved to a later window or shown alternatives."/>
  {isFarmer&&!user.farmer_id&&<Notice>Your account has no linked farmer profile, so a plan cannot be submitted.</Notice>}
  <Panel title="Register planting intent"><form onSubmit={submit} className="formgrid">
   {!isFarmer&&<label>Farmer<select required value={farmer} onChange={e=>setFarmer(e.target.value)}>{farmers.map(f=><option key={f.id} value={f.id}>{f.name} · {f.phone}</option>)}</select></label>}
   <label>Plot (optional)<select value={plot} onChange={e=>setPlot(e.target.value)}><option value="">No specific plot</option>{plots.map(p=><option key={p.id} value={p.id}>{p.acres} acres</option>)}</select></label>
   <label>Crop<select value={crop} onChange={e=>setCrop(e.target.value as CropCode)}>{(crops.length?crops:[{code:'green_gram',name_en:'Green gram'},{code:'maize',name_en:'Maize'},{code:'cowpea',name_en:'Cowpea'},{code:'watermelon',name_en:'Watermelon'}] as Crop[]).map(c=><option key={c.code} value={c.code}>{c.name_en}</option>)}</select></label>
   <label>Area (acres)<input type="number" min=".01" step=".01" required value={acres} onChange={e=>setAcres(e.target.value)}/></label>
   <label>Season<input value={season} onChange={e=>setSeason(e.target.value)}/></label>
   <button className="primary" disabled={busy||!farmer}>{busy?'Saving…':'Submit planting intent'}</button></form></Panel>
  {error&&<Notice>{error}</Notice>}
  {result&&<Panel title="Your planting window"><p>{result.slot?<>Plant between <b>{result.slot.window_start}</b> and <b>{result.slot.window_end}</b>.</>:'No planting window is set for this crop and ward yet.'}</p>{result.warning&&<Notice>{result.warning}</Notice>}{result.alternatives&&result.alternatives.length>0&&<p className="muted">Alternatives: {result.alternatives.map((a:any)=>`${CROP_LABELS[a.crop]||a.crop} (${a.reason})`).join('; ')}</p>}</Panel>}
 </>}
function LotsPage(){const [lots,setLots]=useState<Lot[]>([]),[error,setError]=useState(''),[farmers,setFarmers]=useState<Farmer[]>([]),[farmer,setFarmer]=useState(''),[crop,setCrop]=useState<CropCode>('green_gram'),[weight,setWeight]=useState('500'),[bags,setBags]=useState('5'),[method,setMethod]=useState('hermetic_bag'),[location,setLocation]=useState('Kitui Central store'),[moisture,setMoisture]=useState('12.5'),[created,setCreated]=useState('');useEffect(()=>{api.lots.list().then(r=>setLots(r.results)).catch(e=>setError(e.message));api.farmers.list().then(r=>{setFarmers(r.results);if(r.results[0])setFarmer(r.results[0].id)}).catch(()=>{})},[]);async function registerLot(e:FormEvent){e.preventDefault();setCreated('');setError('');try{const r=await api.lots.create({farmer_id:farmer,crop,weight_kg:Number(weight),bag_count:Number(bags),storage_method:method,location_label:location,moisture_pct:Number(moisture)});setCreated(JSON.stringify(r,null,2));api.lots.list().then(x=>setLots(x.results))}catch(e){setError((e as Error).message)}}return <><PageTitle title="Hifadhi Mavuno" desc="Storage lots, moisture readings and traceable harvest records."/><Panel title="Register a produce lot"><form onSubmit={registerLot} className="formgrid"><label>Farmer<select required value={farmer} onChange={e=>setFarmer(e.target.value)}>{farmers.map(f=><option key={f.id} value={f.id}>{f.name} · {f.phone}</option>)}</select></label><label>Crop<select value={crop} onChange={e=>setCrop(e.target.value as CropCode)}><option value="maize">Maize</option><option value="green_gram">Green gram</option><option value="cowpea">Cowpea</option></select></label><label>Weight (kg)<input type="number" min="0.1" step="0.1" value={weight} onChange={e=>setWeight(e.target.value)}/></label><label>Bag count<input type="number" min="1" value={bags} onChange={e=>setBags(e.target.value)}/></label><label>Storage method<select value={method} onChange={e=>setMethod(e.target.value)}><option value="hermetic_bag">Hermetic bag</option><option value="silo">Silo</option><option value="warehouse">Warehouse</option><option value="other">Other</option></select></label><label>Moisture (%)<input type="number" min="0" max="100" step=".1" value={moisture} onChange={e=>setMoisture(e.target.value)}/></label><label>Storage location<input value={location} onChange={e=>setLocation(e.target.value)}/></label><button className="primary" disabled={!farmer}>Register lot</button></form>{created&&<pre>{created}</pre>}</Panel><div className="toolbar"><span>{lots.length} lots returned</span><span className="pill">Event history is append-only</span></div>{error&&<Notice>{error}</Notice>}<div className="tablewrap"><table><thead><tr><th>Crop</th><th>Initial weight</th><th>Latest weight</th><th>Loss</th><th>Moisture</th><th>Status</th></tr></thead><tbody>{lots.map(l=><tr key={l.id}><td>{l.crop.replace('_',' ')}</td><td>{l.initial_weight_kg} kg</td><td>{l.summary?.latest_weight_kg??'—'} kg</td><td>{l.summary?`${l.summary.loss_kg} kg (${l.summary.loss_pct}%)`:'—'}</td><td>{l.summary?.latest_moisture_pct??'—'}%</td><td><span className="pill">{l.status}</span></td></tr>)}</tbody></table></div><Notice>Loss = initial weight − latest recorded weight. The lot's event history must never be edited or deleted; corrections are new events.</Notice></>}
function FarmersPage(){const [farmers,setFarmers]=useState<Farmer[]>([]),[error,setError]=useState('');useEffect(()=>{api.farmers.list().then(r=>setFarmers(r.results)).catch(e=>setError(e.message))},[]);return <><PageTitle title="Farmers" desc="Farmer records available to your role and cooperative."/><div className="tablewrap"><table><thead><tr><th>Name</th><th>Phone</th><th>Ward</th><th>Consent</th></tr></thead><tbody>{farmers.map(f=><tr key={f.id}><td>{f.name}</td><td>{f.phone}</td><td>{typeof f.ward==='string'?f.ward:f.ward?.name}</td><td>{f.consent_given?'Given':'Not recorded'}</td></tr>)}</tbody></table></div>{error&&<Notice>{error}</Notice>}<p className="muted">Farmer creation requires explicit consent. This list is scoped by the backend user's role and tenant.</p></>}
function WardDashboard(){const [rows,setRows]=useState<{ward:string;crops:DashboardCrop[]}[]>([]),[error,setError]=useState('');useEffect(()=>{let active=true;(async()=>{try{const summaries=await api.dashboard.wards();const details=await Promise.all(summaries.map(s=>api.dashboard.ward(s.id)));if(active)setRows(details.map(d=>({ward:d.ward.name,crops:d.crops})))}catch(e){if(active)setError((e as Error).message)}})();return()=>{active=false}},[]);return <><PageTitle title="Ward dashboard" desc="Cooperative view of planting demand, stored stock and sell-timing flags."/><div className="tablewrap"><table><thead><tr><th>Ward</th><th>Crop</th><th>Intended acres</th><th>Expected demand</th><th>Stored stock</th><th>Avg. loss</th><th>Price/kg</th><th>Signal</th></tr></thead><tbody>{rows.flatMap(r=>r.crops.map(c=><tr key={r.ward+c.crop}><td>{r.ward}</td><td>{c.crop}</td><td>{c.intended_acres??'—'}</td><td>{c.expected_demand_acres??'—'}</td><td>{c.stored_stock_kg??'—'} kg</td><td>{c.avg_loss_pct??'—'}%</td><td>{c.latest_price_per_kg_kes??'—'}</td><td><span className="pill">{c.sell_flag??'—'}</span><small className="block">{c.sell_flag_reason}</small></td></tr>))}</tbody></table></div>{error&&<Notice>{error}</Notice>}<p className="muted">Privacy: ward/crop figures may be suppressed when fewer than five farmers are represented.</p></>}
const VT={
 en:{title:'Confirm your grain record',hello:'Hello',intro:'Your storage agent recorded this grain lot for you. Please check it.',crop:'Crop',stored:'Stored',latest:'Latest weight',loss:'Loss',moisture:'Latest moisture',history:'History',confirm:'Yes, this is correct',dispute:'No, something is wrong',reason:'Tell us what is wrong',send:'Send',cancel:'Cancel',needReason:'Please say what is wrong.',confirmed:'Thank you. Your confirmation has been recorded.',disputed:'Thank you. Your concern has been recorded and your cooperative will follow up.',already:'You have already responded to this link. Thank you.',notFound:'This link was not found. Check that you opened the full link.',expired:'This link has expired. Ask your storage agent for help.',error:'Something went wrong. Please try again later.',loading:'Loading…',privacy:'Only this one lot is shown. Panda Smart never asks for your PIN or money.',other:'Kiswahili'},
 sw:{title:'Thibitisha rekodi ya nafaka yako',hello:'Habari',intro:'Wakala wako wa hifadhi amerekodi nafaka hii kwa ajili yako. Tafadhali ikague.',crop:'Zao',stored:'Iliyohifadhiwa',latest:'Uzito wa mwisho',loss:'Upotevu',moisture:'Unyevu wa mwisho',history:'Historia',confirm:'Ndiyo, hii ni sahihi',dispute:'Hapana, kuna kosa',reason:'Tueleze kosa ni nini',send:'Tuma',cancel:'Ghairi',needReason:'Tafadhali eleza kosa ni nini.',confirmed:'Asante. Uthibitisho wako umerekodiwa.',disputed:'Asante. Malalamiko yako yamerekodiwa na chama chako cha ushirika kitafuatilia.',already:'Tayari umejibu kupitia kiungo hiki. Asante.',notFound:'Kiungo hiki hakijapatikana. Hakikisha umefungua kiungo kamili.',expired:'Muda wa kiungo hiki umeisha. Muulize wakala wako wa hifadhi akusaidie.',error:'Kuna tatizo. Tafadhali jaribu tena baadaye.',loading:'Inapakia…',privacy:'Ni nafaka hii moja tu inayoonyeshwa. Panda Smart haitakuuliza PIN wala pesa.',other:'English'},
};
type VKey=keyof typeof VT.en;
const EVENT_LABELS:Record<string,[string,string]>={REGISTERED:['Grain stored','Nafaka imehifadhiwa'],MOISTURE_READING:['Moisture reading','Kipimo cha unyevu'],WEIGHT_READING:['Weighed','Imepimwa uzito'],CHECKUP:['Check-up','Ukaguzi'],LOSS_RECORDED:['Loss recorded','Upotevu umerekodiwa'],VERIFIED:['You confirmed','Umethibitisha'],DISPUTED:['You disputed','Umelalamika'],CORRECTION:['Correction','Marekebisho']};
function VerifyPage(){
 const {token=''}=useParams();
 const [lang,setLang]=useState<'en'|'sw'>(()=>localStorage.getItem('panda_lang')==='sw'?'sw':'en');
 const t=(k:VKey)=>VT[lang][k];
 const [data,setData]=useState<any>(null),[errKey,setErrKey]=useState<VKey|''>(''),[reason,setReason]=useState(''),[doneKey,setDoneKey]=useState<VKey|''>(''),[busy,setBusy]=useState(false),[disputing,setDisputing]=useState(false),[needReason,setNeedReason]=useState(false);
 function fail(e:unknown){const x=e as ApiError;setErrKey(x.status===404?'notFound':x.code==='conflict'?'expired':'error')}
 useEffect(()=>{api.verify(token).then(setData).catch(fail)},[token]);
 function switchLang(){const next=lang==='en'?'sw':'en';localStorage.setItem('panda_lang',next);setLang(next)}
 async function act(kind:'confirm'|'dispute'){
  if(busy)return;
  if(kind==='dispute'&&!reason.trim()){setNeedReason(true);return}
  setBusy(true);setNeedReason(false);
  try{kind==='confirm'?await api.confirm(token):await api.dispute(token,reason.trim());setDoneKey(kind==='confirm'?'confirmed':'disputed');setData(await api.verify(token).catch(()=>data))}
  catch(e){if((e as ApiError).code==='conflict')setDoneKey('already');else setErrKey('error')}
  finally{setBusy(false)}
 }
 const s=data?.summary,responded=!!doneKey||!!data?.already_responded;
 const num=(v:unknown)=>v==null?'—':Number(v).toLocaleString('en-KE',{maximumFractionDigits:2});
 return <div className="verify"><img src="/panda-smart-logo.png" alt="Panda Smart"/><button type="button" className="secondary" onClick={switchLang}>{t('other')}</button><h1>{t('title')}</h1>
  {errKey?<Notice>{t(errKey)}</Notice>:!data?<p className="muted">{t('loading')}</p>:<>
   <h2>{t('hello')} {data.farmer_name}</h2><p>{t('intro')}</p>
   <div className="tablewrap"><table><tbody>
    <tr><th>{t('crop')}</th><td>{CROP_LABELS[data.lot.crop]||data.lot.crop}</td></tr>
    <tr><th>{t('stored')}</th><td>{num(s.initial_weight_kg)} kg</td></tr>
    <tr><th>{t('latest')}</th><td>{num(s.latest_weight_kg)} kg</td></tr>
    <tr><th>{t('loss')}</th><td>{num(s.loss_kg)} kg ({num(s.loss_pct)}%)</td></tr>
    <tr><th>{t('moisture')}</th><td>{s.latest_moisture_pct==null?'—':`${num(s.latest_moisture_pct)}%`}</td></tr>
   </tbody></table></div>
   {responded?<Notice>{t(doneKey||'already')}</Notice>:disputing?<>
    <label>{t('reason')}<textarea maxLength={500} value={reason} onChange={e=>setReason(e.target.value)}/></label>
    {needReason&&<Notice>{t('needReason')}</Notice>}
    <button className="secondary" disabled={busy} onClick={()=>act('dispute')}>{t('send')}</button> <button className="link" type="button" onClick={()=>setDisputing(false)}>{t('cancel')}</button></>
   :<><button className="primary" disabled={busy} onClick={()=>act('confirm')}>{t('confirm')}</button> <button className="secondary" disabled={busy} onClick={()=>setDisputing(true)}>{t('dispute')}</button></>}
   <h3>{t('history')}</h3>
   <ol>{(data.events||[]).map((ev:any)=><li key={ev.id}><b>{(EVENT_LABELS[ev.type]||[ev.type,ev.type])[lang==='en'?0:1]}</b> <small>{new Date(ev.recorded_at).toLocaleString('en-KE')}</small></li>)}</ol>
   <p className="muted">{t('privacy')}</p></>}
 </div>}
function PageTitle({title,desc}:{title:string;desc:string}){return <div className="page-title"><span className="eyebrow">PANDA SMART</span><h1>{title}</h1><p>{desc}</p></div>}
function Login({onLogin}:{onLogin:(u:User,t:string)=>void}){const [phone,setPhone]=useState(''),[password,setPassword]=useState(''),[showPassword,setShowPassword]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false);async function submit(e:FormEvent){e.preventDefault();setBusy(true);setError('');try{const r=await api.login(phone,password);auth.set(r.token);onLogin(r.user,r.token)}catch(e){setError(e instanceof ApiError?e.message:(e as Error).message)}finally{setBusy(false)}}return <div className="login"><div className="login-card"><img src="/panda-smart-logo.png"/><span className="eyebrow">WELCOME BACK</span><h1>Sign in to Panda Smart</h1><p>Access planting advice, storage records and cooperative insights.</p><form onSubmit={submit}><label>Phone number<input type="tel" autoComplete="username" placeholder="0712 345 678" value={phone} onChange={e=>setPhone(e.target.value)} required/></label><label>Password<div className="password-field"><input type={showPassword?'text':'password'} autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/><button type="button" className="password-toggle" onClick={()=>setShowPassword(v=>!v)} aria-label={showPassword?'Hide password':'Show password'} aria-pressed={showPassword} title={showPassword?'Hide password':'Show password'}>{showPassword?<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.9 5.2A10.8 10.8 0 0112 5c5.2 0 9 5.5 9 7a9.8 9.8 0 01-2.1 3.1M6.2 6.2C3.9 7.8 3 10.7 3 12c0 1.5 3.8 7 9 7 1.1 0 2.1-.2 3-.6"/></svg>:<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.4-7 9.5-7 9.5 7 9.5 7-3.4 7-9.5 7-9.5-7-9.5-7z"/><circle cx="12" cy="12" r="3"/></svg>}</button></div></label><button className="primary" disabled={busy}>{busy?'Signing in…':'Sign in'}</button></form>{error&&<Notice>{error}</Notice>}<small>Use the phone number and password your cooperative registered for you.</small></div></div>}
function AppRoot(){const [user,setUser]=useState<User|null>(null),[checking,setChecking]=useState(!!auth.token());useEffect(()=>{if(auth.token())api.me().then(setUser).catch(()=>auth.clear()).finally(()=>setChecking(false))},[]);const nav=useNavigate();function logout(){api.logout().finally(()=>{setUser(null);nav('/')})}
 useEffect(()=>{const h=()=>setUser(null);window.addEventListener('panda:unauthorized',h);return()=>window.removeEventListener('panda:unauthorized',h)},[]);if(checking)return <div className="loading">Loading Panda Smart…</div>;return <Routes><Route path="/verify/:token" element={<VerifyPage/>}/><Route path="*" element={user?<Shell user={user} onLogout={logout}/>:<Login onLogin={u=>setUser(u)}/>} /></Routes>}
export function App(){return <BrowserRouter><AppRoot/></BrowserRouter>}
