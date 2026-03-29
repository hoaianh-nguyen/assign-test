from flask import Flask, jsonify, render_template, request
import pandas as pd, numpy as np, os, math, glob

app = Flask(__name__)

def find_xlsx():
    here = os.path.dirname(os.path.abspath(__file__))
    files = glob.glob(os.path.join(here, '*.xlsx'))
    return files[0] if files else None

DATA_PATH = find_xlsx()
print("Excel: " + str(DATA_PATH), flush=True)

DF = None

def load():
    global DF
    if not DATA_PATH:
        raise FileNotFoundError("No .xlsx found")
    df = pd.read_excel(DATA_PATH)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={
        'order id': 'order_id', 'current step': 'current_step',
        'incharge long': 'incharge_long', 'incharge lat': 'incharge_lat',
        'pick long': 'pick_long', 'pick lat': 'pick_lat',
        'drop long': 'drop_long', 'drop lat': 'drop_lat',
        'wave ID': 'wave_id', 'wave type': 'wave_type',
    })
    for c in ['created_timestamp', 'last_incharge_timestamp',
              'last_picked_timestamp', 'last_delivered_timestamp']:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors='coerce')
    for c in ['ata_segment', 'lt_completion', 'delivery_distance', 'wave_type']:
        if c not in df.columns:
            df[c] = np.nan
    print(str(len(df)) + " rows | " + str(df['shipper_id'].nunique()) + " drivers | " + str(df['order_id'].nunique()) + " orders", flush=True)
    return df

try:
    DF = load()
except Exception as e:
    print("Load failed: " + str(e), flush=True)

def fmt(ts):
    try:
        return ts.strftime('%H:%M') if not pd.isnull(ts) else None
    except:
        return None

def flt(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except:
        return None

def is_ontime(seg):
    return 'Ontime' in str(seg) if not pd.isnull(seg) else False

def no_data():
    return jsonify(error='Data not loaded'), 503

def order_to_dict(r, oid):
    def xy(lc, lac):
        a, b = flt(r.get(lc)), flt(r.get(lac))
        return [a, b] if a and b else None
    return dict(
        order_id=str(oid),
        shipper_id=int(r['shipper_id']),
        assign_type=str(r.get('assign_type', '')),
        wave_type=str(r.get('wave_type', '')),
        ata_segment=str(r.get('ata_segment', '')),
        ontime=is_ontime(r.get('ata_segment')),
        lt_min=round(flt(r['lt_completion']) / 60, 1) if flt(r['lt_completion']) else None,
        distance_km=round(flt(r['delivery_distance']) / 1000, 2) if flt(r['delivery_distance']) else None,
        created_ts=fmt(r['created_timestamp']),
        incharge_ts=fmt(r['last_incharge_timestamp']),
        pick_ts=fmt(r['last_picked_timestamp']),
        drop_ts=fmt(r['last_delivered_timestamp']),
        incharge=xy('incharge_long', 'incharge_lat'),
        pick=xy('pick_long', 'pick_lat'),
        drop=xy('drop_long', 'drop_lat'),
        current_step=str(r.get('current_step', ''))
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/summary')
def summary():
    if DF is None: return no_data()
    n = int(DF['order_id'].nunique())
    d = int(DF['shipper_id'].nunique())
    u = DF.drop_duplicates('order_id')
    ot = int(u['ata_segment'].apply(is_ontime).sum())
    return jsonify(total_orders=n, total_drivers=d, ontime=ot,
                   late=n - ot, ontime_pct=round(ot / n * 100, 1) if n else 0)

@app.route('/api/drivers')
def get_drivers():
    if DF is None: return no_data()
    out = []
    for sid, g in DF.groupby('shipper_id'):
        u = g.drop_duplicates('order_id')
        t = len(u)
        ot = int(u['ata_segment'].apply(is_ontime).sum())
        out.append(dict(id=int(sid), orders=t, ontime=ot, late=t - ot))
    out.sort(key=lambda x: x['orders'], reverse=True)
    return jsonify(out)

@app.route('/api/driver/<int:shipper_id>')
def get_driver(shipper_id):
    if DF is None: return no_data()
    g = DF[DF['shipper_id'] == shipper_id]
    if g.empty: return jsonify(error='Not found'), 404
    orders = []
    for oid, og in g.groupby('order_id'):
        r = og.iloc[0]
        orders.append(order_to_dict(r, oid))
    orders.sort(key=lambda x: x['incharge_ts'] or '')
    t = len(orders)
    ot = sum(1 for o in orders if o['ontime'])
    return jsonify(shipper_id=shipper_id, total=t, ontime=ot, late=t - ot, orders=orders)

@app.route('/api/timeslots')
def timeslots():
    if DF is None: return no_data()
    ts = DF['last_incharge_timestamp'].dropna()
    if ts.empty: return jsonify([])
    mn = ts.min().floor('5min')
    mx = ts.max().ceil('5min')
    slots = []
    cur = mn
    while cur <= mx:
        nxt = cur + pd.Timedelta(minutes=5)
        mask = (DF['last_incharge_timestamp'] >= cur) & (DF['last_incharge_timestamp'] < nxt)
        sub = DF[mask]
        cnt = int(sub['order_id'].nunique())
        if cnt > 0:
            slots.append(dict(
                slot=cur.strftime('%H:%M'),
                slot_end=nxt.strftime('%H:%M'),
                count=cnt,
                drivers=int(sub['shipper_id'].nunique())
            ))
        cur = nxt
    return jsonify(slots)

@app.route('/api/slot_orders')
def slot_orders():
    if DF is None: return no_data()
    slots = request.args.getlist('slots')  # list of "HH:MM" start times
    if not slots: return jsonify(orders=[], created_only=[])

    # Build mask for selected slots
    mask = pd.Series([False] * len(DF), index=DF.index)
    for s in slots:
        h, m = int(s.split(':')[0]), int(s.split(':')[1])
        slot_start = DF['last_incharge_timestamp'].dt.normalize() + pd.Timedelta(hours=h, minutes=m)
        slot_end   = slot_start + pd.Timedelta(minutes=5)
        mask |= (DF['last_incharge_timestamp'] >= slot_start) & (DF['last_incharge_timestamp'] < slot_end)

    in_slot = DF[mask]
    # Unique orders in selected slots
    orders = []
    seen = set()
    for oid, og in in_slot.groupby('order_id'):
        if oid in seen: continue
        seen.add(oid)
        r = og.iloc[0]
        orders.append(order_to_dict(r, oid))

    # Orders that ONLY have created_timestamp in the window (not yet incharged)
    # i.e., created before max slot end, but incharge_ts NOT in selected slots
    all_oids_in_slot = set(in_slot['order_id'].unique())
    created_only = []
    for oid, og in DF[~mask].groupby('order_id'):
        if oid in all_oids_in_slot: continue
        r = og.iloc[0]
        if pd.isnull(r['created_timestamp']): continue
        d = order_to_dict(r, oid)
        if d['incharge'] or d['pick'] or d['drop']:
            created_only.append(d)

    orders.sort(key=lambda x: x['incharge_ts'] or '')
    return jsonify(orders=orders, created_only=created_only[:300])

if __name__ == '__main__':
    app.run(debug=True, port=5001)
