# ============================================================
#  ShipTrack — app.py
#  Run: python3 app.py
#  Requires: pip install flask pandas openpyxl
# ============================================================
from flask import Flask, jsonify, render_template_string
import pandas as pd, numpy as np, os, math, glob

app = Flask(__name__)

# ── 1. Find the Excel file (any .xlsx in same folder) ────────
def find_xlsx():
    here = os.path.dirname(os.path.abspath(__file__))
    files = glob.glob(os.path.join(here, '*.xlsx'))
    return files[0] if files else None

DATA_PATH = find_xlsx()
print(f"\n{'✅' if DATA_PATH else '❌'}  Excel: {DATA_PATH}\n", flush=True)

# ── 2. Load & clean data ─────────────────────────────────────
DF = None

def load():
    global DF
    if not DATA_PATH:
        raise FileNotFoundError("No .xlsx found next to app.py")
    df = pd.read_excel(DATA_PATH)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={
        'order id':'order_id', 'current step':'current_step',
        'incharge long':'incharge_long', 'incharge lat':'incharge_lat',
        'pick long':'pick_long', 'pick lat':'pick_lat',
        'drop long':'drop_long', 'drop lat':'drop_lat',
        'wave ID':'wave_id', 'wave type':'wave_type',
    })
    for c in ['created_timestamp','last_incharge_timestamp',
              'last_picked_timestamp','last_delivered_timestamp']:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors='coerce')
    for c in ['ata_segment','lt_completion','delivery_distance','wave_type']:
        if c not in df.columns:
            df[c] = np.nan
    print(f"✅  {len(df)} rows | {df['shipper_id'].nunique()} drivers | {df['order_id'].nunique()} orders\n", flush=True)
    return df

try:
    DF = load()
except Exception as e:
    print(f"❌  {e}\n", flush=True)

# ── 3. Helpers ───────────────────────────────────────────────
def fmt(ts):
    try: return ts.strftime('%H:%M') if not pd.isnull(ts) else None
    except: return None

def flt(v):
    try:
        f = float(v); return None if math.isnan(f) else f
    except: return None

def is_ontime(seg):
    return 'Ontime' in str(seg) if not pd.isnull(seg) else False

def no_data():
    return jsonify(error='Data not loaded — check terminal'), 503

# ── 4. HTML (inline so no templates/ folder needed) ──────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShipTrack</title>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{--bg:#0d1117;--sb:#111827;--panel:#1a2332;--border:rgba(255,255,255,.07);--text:#e2e8f0;--muted:#64748b;--accent:#38bdf8;--green:#4ade80;--red:#f87171;--yellow:#fbbf24;--fn:'Sora',sans-serif;--mo:'JetBrains Mono',monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--fn);background:var(--bg);color:var(--text);height:100vh;display:flex;overflow:hidden}
#sidebar{width:300px;min-width:300px;background:var(--sb);border-right:1px solid var(--border);display:flex;flex-direction:column;height:100vh;z-index:10}
.sh{padding:16px 16px 12px;border-bottom:1px solid var(--border)}
.logo{display:flex;align-items:center;gap:9px;margin-bottom:12px}
.logo-icon{width:30px;height:30px;background:linear-gradient(135deg,#38bdf8,#818cf8);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px}
.logo-text{font-size:15px;font-weight:700}.logo-text span{color:var(--accent)}
.sr{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}
.sc{background:var(--panel);border:1px solid var(--border);border-radius:7px;padding:7px;text-align:center}
.sc .v{font-size:15px;font-weight:700;font-family:var(--mo);display:block}
.sc .l{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.sc.blue .v{color:var(--accent)}.sc.green .v{color:var(--green)}.sc.red .v{color:var(--red)}
.sw{padding:9px 14px 7px;border-bottom:1px solid var(--border)}
.sb{position:relative}
.sb input{width:100%;background:var(--panel);border:1px solid var(--border);border-radius:7px;padding:7px 10px 7px 30px;color:var(--text);font-family:var(--fn);font-size:12px;outline:none;transition:border-color .2s}
.sb input:focus{border-color:var(--accent)}.sb input::placeholder{color:var(--muted)}
.si{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:12px;pointer-events:none}
.fr{display:flex;gap:4px;margin-top:6px}
.fb{flex:1;background:var(--panel);border:1px solid var(--border);border-radius:5px;padding:4px 5px;color:var(--muted);font-family:var(--fn);font-size:10px;cursor:pointer;text-align:center;transition:all .15s}
.fb:hover,.fb.active{border-color:var(--accent);color:var(--accent);background:rgba(56,189,248,.08)}
.sl{padding:5px 14px;font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}
.dl{flex:1;overflow-y:auto;padding:3px 0}
.dl::-webkit-scrollbar{width:3px}.dl::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.di{display:flex;align-items:center;gap:9px;padding:8px 14px;cursor:pointer;transition:background .15s;border-left:3px solid transparent}
.di:hover{background:var(--panel)}.di.active{background:rgba(56,189,248,.07);border-left-color:var(--accent)}
.di input[type=checkbox]{width:13px;height:13px;accent-color:var(--accent);cursor:pointer;flex-shrink:0}
.da{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;font-family:var(--mo);flex-shrink:0;color:#fff}
.di-info{flex:1;min-width:0}
.di-id{font-size:11px;font-weight:600;font-family:var(--mo);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.di-meta{display:flex;align-items:center;gap:4px;margin-top:1px}
.di-meta span{font-size:9px;color:var(--muted)}
.bx{display:inline-flex;padding:1px 5px;border-radius:3px;font-size:8px;font-weight:600;font-family:var(--mo)}
.bx.green{background:rgba(74,222,128,.12);color:var(--green)}.bx.red{background:rgba(248,113,113,.12);color:var(--red)}.bx.gray{background:rgba(100,116,139,.15);color:var(--muted)}
.dc{font-family:var(--mo);font-size:11px;font-weight:700;color:var(--muted);flex-shrink:0}
#mw{flex:1;position:relative;overflow:hidden}
#map{width:100%;height:100%}
.mt{position:absolute;top:0;left:0;right:0;z-index:500;background:linear-gradient(to bottom,rgba(13,17,23,.85),transparent);padding:11px 16px;display:flex;align-items:center;justify-content:space-between;pointer-events:none}
.mt-t{font-size:12px;font-weight:600}.mt-d{font-size:11px;color:var(--muted);font-family:var(--mo)}
.leg{position:absolute;bottom:20px;left:16px;z-index:500;background:rgba(17,24,39,.93);backdrop-filter:blur(8px);border:1px solid var(--border);border-radius:10px;padding:9px 12px;font-size:11px;pointer-events:none}
.lt{font-size:9px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px;font-weight:600}
.li{display:flex;align-items:center;gap:6px;margin-bottom:3px;color:var(--text)}
.ld{width:8px;height:8px;border-radius:50%;flex-shrink:0}
#card{position:absolute;top:46px;right:16px;z-index:600;width:280px;background:rgba(17,24,39,.97);backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:13px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.5);display:none;animation:si .22s ease}
@keyframes si{from{opacity:0;transform:translateX(16px)}to{opacity:1;transform:translateX(0)}}
.ch{padding:13px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px}
.ca{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;font-family:var(--mo);color:#fff;flex-shrink:0}
.cn{font-size:9px;font-family:var(--mo);font-weight:600;color:var(--accent);letter-spacing:.5px}
.ci{font-size:13px;font-weight:700;font-family:var(--mo);margin:1px 0}
.cs2{font-size:8px;padding:2px 5px;border-radius:20px;font-weight:600;background:rgba(74,222,128,.15);color:var(--green)}
.cst{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--border);border-bottom:1px solid var(--border)}
.cx{background:var(--panel);padding:9px 7px;text-align:center}
.cx .n{font-size:17px;font-weight:700;font-family:var(--mo);display:block}.cx .l{font-size:8px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.col{max-height:280px;overflow-y:auto;padding:5px 0}
.col::-webkit-scrollbar{width:3px}.col::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.or{padding:8px 12px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .1s}
.or:hover{background:rgba(56,189,248,.05)}.or:last-child{border-bottom:none}
.ot{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px}
.on{font-family:var(--mo);font-size:9px;font-weight:600;color:var(--accent)}
.tl{display:flex;align-items:center}
.ts{display:flex;flex-direction:column;align-items:center;gap:2px}
.td{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.tt{font-size:7px;font-family:var(--mo);color:var(--muted);white-space:nowrap}
.tln{flex:1;height:2px;min-width:14px;margin-bottom:9px}
.td.c{background:#64748b}.td.i{background:var(--accent)}.td.p{background:var(--yellow)}.td.d{background:var(--green)}
.tln.l1{background:linear-gradient(90deg,#64748b,var(--accent))}.tln.l2{background:linear-gradient(90deg,var(--accent),var(--yellow))}.tln.l3{background:linear-gradient(90deg,var(--yellow),var(--green))}
.cc{position:absolute;top:9px;right:11px;background:rgba(255,255,255,.07);border:none;border-radius:5px;width:22px;height:22px;color:var(--muted);cursor:pointer;font-size:11px;display:flex;align-items:center;justify-content:center;transition:all .15s}
.cc:hover{background:rgba(248,113,113,.15);color:var(--red)}
#spin{display:none;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:999}
.sr2{width:34px;height:34px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:rr .7s linear infinite}
@keyframes rr{to{transform:rotate(360deg)}}
#eb{display:none;position:absolute;top:46px;left:50%;transform:translateX(-50%);z-index:800;background:rgba(248,113,113,.15);border:1px solid rgba(248,113,113,.4);border-radius:7px;padding:8px 16px;color:var(--red);font-size:11px;white-space:nowrap;animation:si .2s ease}
.empty{text-align:center;padding:32px 14px;color:var(--muted);font-size:11px}
.leaflet-popup-content-wrapper{background:rgba(17,24,39,.97)!important;border:1px solid var(--border)!important;border-radius:9px!important;box-shadow:0 8px 30px rgba(0,0,0,.4)!important;font-family:var(--fn)!important}
.leaflet-popup-tip{background:rgba(17,24,39,.97)!important}
.leaflet-popup-content{font-family:var(--fn)!important;font-size:11px!important;margin:9px 12px!important;color:var(--text)!important}
.pon{font-family:var(--mo);color:var(--accent);font-weight:600;font-size:10px}
.pr{display:flex;justify-content:space-between;gap:12px;margin-top:3px}
.pr .k{color:var(--muted)}.pr .v{font-weight:600;font-family:var(--mo)}
.pd{border:none;border-top:1px solid var(--border);margin:4px 0}
</style>
</head>
<body>
<div id="sidebar">
  <div class="sh">
    <div class="logo"><div class="logo-icon">🚚</div><div class="logo-text">Ship<span>Track</span></div></div>
    <div class="sr">
      <div class="sc blue"><span class="v" id="gd">—</span><span class="l">Drivers</span></div>
      <div class="sc green"><span class="v" id="got">—</span><span class="l">On-Time</span></div>
      <div class="sc red"><span class="v" id="gl">—</span><span class="l">Late</span></div>
    </div>
  </div>
  <div class="sw">
    <div class="sb"><span class="si">🔍</span><input id="qi" type="text" placeholder="Search driver ID…"></div>
    <div class="fr">
      <button class="fb active" onclick="sf(this,'all')">All</button>
      <button class="fb" onclick="sf(this,'ontime')">On-Time</button>
      <button class="fb" onclick="sf(this,'late')">Late</button>
    </div>
  </div>
  <div class="sl" id="lbl">Loading…</div>
  <div class="dl" id="dl"></div>
</div>

<div id="mw">
  <div class="mt"><div class="mt-t">📍 Ha Noi City — Delivery Map</div><div class="mt-d">2026-08-03</div></div>
  <div id="map"></div>
  <div class="leg">
    <div class="lt">Route Stages</div>
    <div class="li"><div class="ld" style="background:#64748b"></div>Created</div>
    <div class="li"><div class="ld" style="background:#38bdf8"></div>Incharge</div>
    <div class="li"><div class="ld" style="background:#fbbf24"></div>Pickup</div>
    <div class="li"><div class="ld" style="background:#4ade80"></div>Drop-off</div>
  </div>
  <div id="card">
    <button class="cc" onclick="closeCard()">✕</button>
    <div class="ch">
      <div class="ca" id="ca">DR</div>
      <div><div class="cn">DRIVER ID</div><div class="ci" id="cid">—</div><span class="cs2">● ACTIVE</span></div>
    </div>
    <div class="cst">
      <div class="cx"><span class="n" id="ct">—</span><span class="l">Orders</span></div>
      <div class="cx"><span class="n" id="co" style="color:var(--green)">—</span><span class="l">On-Time</span></div>
      <div class="cx"><span class="n" id="cla" style="color:var(--red)">—</span><span class="l">Late</span></div>
    </div>
    <div class="col" id="col"></div>
  </div>
  <div id="spin"><div class="sr2"></div></div>
  <div id="eb"></div>
</div>

<script>
const PAL=['#38bdf8','#818cf8','#f472b6','#fb923c','#a78bfa','#34d399','#fbbf24','#60a5fa','#f87171','#4ade80','#e879f9','#2dd4bf'];
const HANOI=[21.0278,105.8342];
let ALL=[],ROUTES={},FILTER='all',SEL=null;

const map=L.map('map',{center:HANOI,zoom:13,zoomControl:false,attributionControl:false});
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{maxZoom:19}).addTo(map);
L.control.zoom({position:'bottomright'}).addTo(map);

const col=id=>PAL[Math.abs(id)%PAL.length];
const ini=id=>String(id).slice(-2);
const spin=v=>document.getElementById('spin').style.display=v?'flex':'none';

function showErr(msg){
  const e=document.getElementById('eb');
  e.textContent='⚠️ '+msg; e.style.display='block';
  setTimeout(()=>e.style.display='none',5000);
}

async function get(url){
  const r=await fetch(url);
  if(!r.ok){const b=await r.json().catch(()=>({}));throw new Error(b.error||'HTTP '+r.status);}
  return r.json();
}

async function loadSummary(){
  try{
    const d=await get('/api/summary');
    document.getElementById('gd').textContent=d.total_drivers;
    document.getElementById('got').textContent=d.ontime_pct+'%';
    document.getElementById('gl').textContent=d.late;
  }catch(e){showErr('Summary: '+e.message);console.error(e);}
}

async function loadDrivers(){
  try{
    ALL=await get('/api/drivers');
    render(ALL);
  }catch(e){
    document.getElementById('lbl').textContent='Error loading drivers';
    showErr('Drivers: '+e.message);console.error(e);
  }
}

function sf(btn,f){
  document.querySelectorAll('.fb').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); FILTER=f; applyFilter();
}

function applyFilter(){
  const q=document.getElementById('qi').value.toLowerCase();
  let list=ALL;
  if(FILTER==='ontime') list=list.filter(d=>d.ontime>=d.late);
  if(FILTER==='late')   list=list.filter(d=>d.late>d.ontime);
  if(q) list=list.filter(d=>String(d.id).includes(q));
  render(list);
}

function render(drivers){
  const el=document.getElementById('dl');
  document.getElementById('lbl').textContent=drivers.length+' driver'+(drivers.length!==1?'s':'');
  if(!drivers.length){el.innerHTML='<div class="empty">🔍<br>No drivers match</div>';return;}
  el.innerHTML=drivers.map(d=>{
    const c=col(d.id),chk=ROUTES[d.id]?'checked':'',act=SEL===d.id?'active':'';
    const pct=d.orders?Math.round(d.ontime/d.orders*100):0;
    return`<div class="di ${act}" id="i${d.id}" onclick="selDriver(${d.id})">
      <div onclick="event.stopPropagation()"><input type="checkbox" id="k${d.id}" ${chk} onchange="togRoute(${d.id},this.checked)"></div>
      <div class="da" style="background:${c}22;border:1.5px solid ${c}40;color:${c}">${ini(d.id)}</div>
      <div class="di-info">
        <div class="di-id">${d.id}</div>
        <div class="di-meta"><span>${d.orders} orders</span><span class="bx ${pct>=50?'green':'red'}">${pct}% OT</span></div>
      </div>
      <div class="dc" style="color:${c}">${d.orders}</div>
    </div>`;
  }).join('');
}

document.getElementById('qi').addEventListener('input',applyFilter);

async function togRoute(id,show){if(show)await drawRoute(id);else clearRoute(id);}

function clearRoute(id){
  if(ROUTES[id]){ROUTES[id].layers.forEach(l=>map.removeLayer(l));delete ROUTES[id];}
}

async function drawRoute(id){
  if(ROUTES[id])return;
  spin(true);
  try{
    const data=await get('/api/driver/'+id);
    const c=col(id),layers=[];
    data.orders.forEach(o=>{
      const pts=[];
      if(o.incharge)pts.push({pos:[o.incharge[1],o.incharge[0]],step:'incharge',ts:o.incharge_ts});
      if(o.pick)    pts.push({pos:[o.pick[1],    o.pick[0]],    step:'pick',    ts:o.pick_ts});
      if(o.drop)    pts.push({pos:[o.drop[1],    o.drop[0]],    step:'drop',    ts:o.drop_ts});
      if(pts.length<2)return;
      layers.push(L.polyline(pts.map(p=>p.pos),{color:c,weight:3,opacity:.85,smoothFactor:1.5}).addTo(map));
      pts.forEach(pt=>{
        const dc=pt.step==='incharge'?'#38bdf8':pt.step==='pick'?'#fbbf24':'#4ade80';
        const icon=L.divIcon({className:'',html:`<div style="width:9px;height:9px;background:${dc};border:2px solid #0d1117;border-radius:50%;box-shadow:0 0 6px ${dc}88"></div>`,iconAnchor:[5,5]});
        layers.push(L.marker(pt.pos,{icon}).bindPopup(mkPopup(o,pt.step,dc)).addTo(map));
        if(pt.ts&&pt.step!=='incharge'){
          const bi=L.divIcon({className:'',html:`<div style="background:${dc};color:#0d1117;font-family:'JetBrains Mono',monospace;font-size:8px;font-weight:700;padding:2px 4px;border-radius:3px;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,.3)">${pt.ts}</div>`,iconAnchor:[-5,4]});
          layers.push(L.marker(pt.pos,{icon:bi,interactive:false}).addTo(map));
        }
      });
    });
    ROUTES[id]={layers,c,data};
  }catch(e){showErr('Driver '+id+': '+e.message);console.error(e);}
  finally{spin(false);}
}

function mkPopup(o,step,dc){
  return`<div class="pon">Order #${o.order_id}</div>
    <div class="pr"><span class="k">Stage</span><span class="v" style="color:${dc}">${step.toUpperCase()}</span></div>
    <hr class="pd">
    <div class="pr"><span class="k">Status</span><span class="v" style="color:${o.ontime?'#4ade80':'#f87171'}">${o.ata_segment}</span></div>
    <div class="pr"><span class="k">Duration</span><span class="v">${o.lt_min?o.lt_min+'min':'—'}</span></div>
    <div class="pr"><span class="k">Type</span><span class="v">${o.assign_type}</span></div>
    <hr class="pd">
    <div class="pr"><span class="k">Incharge</span><span class="v">${o.incharge_ts||'—'}</span></div>
    <div class="pr"><span class="k">Pick</span><span class="v">${o.pick_ts||'—'}</span></div>
    <div class="pr"><span class="k">Drop</span><span class="v">${o.drop_ts||'—'}</span></div>`;
}

async function selDriver(id){
  SEL=id;
  document.querySelectorAll('.di').forEach(e=>e.classList.remove('active'));
  const item=document.getElementById('i'+id);
  if(item){item.classList.add('active');item.scrollIntoView({block:'nearest',behavior:'smooth'});}
  const chk=document.getElementById('k'+id);
  if(chk&&!chk.checked)chk.checked=true;
  if(!ROUTES[id])await drawRoute(id);
  if(ROUTES[id]){
    const pts=[];
    ROUTES[id].layers.forEach(l=>{
      if(l.getLatLngs){const a=l.getLatLngs();(Array.isArray(a[0])?a[0]:a).forEach(p=>pts.push(p));}
      else if(l.getLatLng)pts.push(l.getLatLng());
    });
    if(pts.length)map.fitBounds(L.latLngBounds(pts).pad(0.15));
  }
  const c=col(id),data=ROUTES[id]?.data;
  const av=document.getElementById('ca');
  av.style.background=c+'22';av.style.border=`2px solid ${c}60`;av.style.color=c;av.textContent=ini(id);
  document.getElementById('cid').textContent=id;
  if(data){
    document.getElementById('ct').textContent=data.total;
    document.getElementById('co').textContent=data.ontime;
    document.getElementById('cla').textContent=data.late;
    document.getElementById('col').innerHTML=data.orders.map(o=>`
      <div class="or" onclick='focOrd(${JSON.stringify(o)})'>
        <div class="ot"><span class="on">#${o.order_id}</span><span class="bx ${o.ontime?'green':'red'}">${o.ontime?'✓ OT':'✗ Late'}</span></div>
        <div class="tl">
          <div class="ts"><div class="td c"></div><div class="tt">${o.created_ts||'—'}</div></div>
          <div class="tln l1"></div>
          <div class="ts"><div class="td i"></div><div class="tt">${o.incharge_ts||'—'}</div></div>
          <div class="tln l2"></div>
          <div class="ts"><div class="td p"></div><div class="tt">${o.pick_ts||'—'}</div></div>
          <div class="tln l3"></div>
          <div class="ts"><div class="td d"></div><div class="tt">${o.drop_ts||'—'}</div></div>
        </div>
        <div style="margin-top:3px;display:flex;gap:4px;flex-wrap:wrap">
          ${o.lt_min?`<span class="bx gray">⏱${o.lt_min}m</span>`:''}
          ${o.distance_km?`<span class="bx gray">📍${o.distance_km}km</span>`:''}
          <span class="bx gray">${o.assign_type}</span>
        </div>
      </div>`).join('');
  }
  document.getElementById('card').style.display='block';
}

function focOrd(o){const pt=o.pick||o.drop;if(pt)map.setView([pt[1],pt[0]],15,{animate:true});}
function closeCard(){document.getElementById('card').style.display='none';SEL=null;document.querySelectorAll('.di').forEach(e=>e.classList.remove('active'));}

(async()=>{await Promise.all([loadSummary(),loadDrivers()]);})();
</script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/debug')
def debug():
    return jsonify(excel=DATA_PATH, rows=int(len(DF)) if DF is not None else None,
                   drivers=int(DF['shipper_id'].nunique()) if DF is not None else None)

@app.route('/api/summary')
def summary():
    if DF is None: return no_data()
    n = int(DF['order_id'].nunique())
    d = int(DF['shipper_id'].nunique())
    u = DF.drop_duplicates('order_id')
    ot = int(u['ata_segment'].apply(is_ontime).sum())
    return jsonify(total_orders=n, total_drivers=d, ontime=ot,
                   late=n-ot, ontime_pct=round(ot/n*100,1) if n else 0)

@app.route('/api/drivers')
def get_drivers():
    if DF is None: return no_data()
    out=[]
    for sid, g in DF.groupby('shipper_id'):
        u=g.drop_duplicates('order_id'); t=len(u)
        ot=int(u['ata_segment'].apply(is_ontime).sum())
        out.append(dict(id=int(sid),orders=t,ontime=ot,late=t-ot))
    out.sort(key=lambda x:x['orders'],reverse=True)
    return jsonify(out)

@app.route('/api/driver/<int:shipper_id>')
def get_driver(shipper_id):
    if DF is None: return no_data()
    g=DF[DF['shipper_id']==shipper_id]
    if g.empty: return jsonify(error='Not found'),404
    orders=[]
    for oid,og in g.groupby('order_id'):
        r=og.iloc[0]
        def xy(lc,lac):
            a,b=flt(r.get(lc)),flt(r.get(lac))
            return [a,b] if a and b else None
        orders.append(dict(
            order_id=str(oid), assign_type=str(r.get('assign_type','')),
            wave_type=str(r.get('wave_type','')), ata_segment=str(r.get('ata_segment','')),
            ontime=is_ontime(r.get('ata_segment')),
            lt_min=round(flt(r['lt_completion'])/60,1) if flt(r['lt_completion']) else None,
            distance_km=round(flt(r['delivery_distance'])/1000,2) if flt(r['delivery_distance']) else None,
            created_ts=fmt(r['created_timestamp']), incharge_ts=fmt(r['last_incharge_timestamp']),
            pick_ts=fmt(r['last_picked_timestamp']), drop_ts=fmt(r['last_delivered_timestamp']),
            incharge=xy('incharge_long','incharge_lat'), pick=xy('pick_long','pick_lat'),
            drop=xy('drop_long','drop_lat'), current_step=str(r.get('current_step',''))
        ))
    orders.sort(key=lambda x:x['incharge_ts'] or '')
    t=len(orders); ot=sum(1 for o in orders if o['ontime'])
    return jsonify(shipper_id=shipper_id,total=t,ontime=ot,late=t-ot,orders=orders)

if __name__=='__main__':
    app.run(debug=True, port=5001)
