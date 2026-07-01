#!/usr/bin/env python3
"""
出入库管理系统 - 后端API服务器
支持多人联网，数据通过金山文档共享
"""

import json, os, time, hashlib, random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# 获取当前文件所在目录（兼容本地和云部署）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
CORS(app)

# ============ WPS 同步模块 ============
try:
    from wps_sync import (
        push_outbound_batch, push_inbound_batch, push_inventory,
        full_push, init_wps_sheets, get_wps_status,
        pull_all_and_replace,
        get_status as get_sync_status, set_enabled, reset_errors,
    )
    WPS_SYNC_ENABLED = True
except ImportError:
    WPS_SYNC_ENABLED = False
    print('[WPS] wps_sync.py 未找到，WPS 同步功能已禁用')

# ============ 配置 ============
KDOCS_TOKEN = os.environ.get('KDOCS_TOKEN', '')
KDOCS_FILE_ID = os.environ.get('KDOCS_FILE_ID', '')

# ============ 用户管理 ============
USERS = {
    '1': {'password': '', 'role': 'admin', 'name': '管理员'},
    'finance': {'password': '123456', 'role': 'finance', 'name': '财务'},
    'operator': {'password': '', 'role': 'operator', 'name': '登记员'},
}

ROLE_PERMS = {
    'admin': ['all'],
    'finance': ['view_finance', 'view_records', 'view_stock', 'reconciliation'],
    'operator': ['inbound', 'outbound', 'view_stock', 'view_records'],
}

def require_role(*roles):
    s = get_session()
    if not s: return None
    if 'admin' in roles and s.get('role') == 'admin': return s
    if s.get('role') in roles: return s
    return None

def require_auth():
    return require_role('admin', 'finance', 'operator')

# ============ 会话管理 ============
sessions = {}

def get_session():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    return sessions.get(token)

def require_auth():
    s = get_session()
    if not s: return None
    return s

def require_admin():
    return require_role('admin')

# ============ 数据存储（内存缓存 + 持久化文件） ============
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
data_lock = __import__('threading').Lock()

DEFAULT_CONFIG = {
    'warehouses': ['广州百脑汇仓', '深圳大我仓'],
    'accounts': ['广州彩次元', '广东北斗', '华个人帐', '售后换新', '门店销售'],
    'customers': ['PDD彩次元', 'JD个人', 'TB个人', 'XY个人', 'DY个人', '门店销售', '公对公'],
    'suppliers': ['深圳大我', '深圳国阅', '广州格凡', '发票补开'],
    'materials': {
        '6973555480693':'大我B13','6973555480891':'大我B7pro-C绿色','6973555480907':'大我B7pro-C白色',
        '6973555480884':'大我B7pro-C蓝色','6973555481027粉':'大我B7皮套粉红色','6973555481027蓝':'大我B7皮套蓝色',
        '6973555481027灰':'大我B7皮套灰色','6973555480662白':'大我B651皮套白色','6973555480662黑':'大我B651皮套黑色',
        '6973555480730':'大我B6C黑色','6973555480761':'大我B6C绿色','6973555480754':'大我B6C白色',
        '6973555480723蓝':'大我B6皮套蓝色','6973555480723粉':'大我B6皮套粉色','6973555480723紫':'大我B6皮套紫色',
        '6973555480723绿':'大我B6皮套绿色','6973555480709':'B531CS大我HiBreak-S-C白色',
        '6973555480778':'B531S大我HiBreak-S-BW白色','6973555481003':'HiBreak plus C白色',
        '6973555480792':'B651C大我HiBreak pro-C白色','6973555480808':'B651C大我HiBreak pro-C黑色',
        '6973555480938':'大我B10-C白色','6973555481065蓝':'大我B10皮套蓝色',
        '6973555480600':'大我B1051c pro','6973555480815':'大我B751电容笔（C1）',
        '6974417015558':'国悦K3Color','BMA5B':'大我A5电磁笔','BMA3B':'大我A3电磁笔',
        'BMC7B':'大我C7电容笔','BMCBX':'大我C1/C7系列笔芯','BMB5PT':'大我B5磁吸皮套',
        'BMS6PT':'大我S6磁吸皮套','6973555480617':'B651大我HiBreak pro-BW白色',
        '6973555480686':'B651大我HiBreak pro-BW黑色','6973555480679':'大我B7蓝色',
    }
}

def load_data():
    with data_lock:
        try:
            with open(DATA_FILE, 'r') as f:
                d = json.load(f)
                if 'config' not in d:
                    d['config'] = DEFAULT_CONFIG
                return d
        except:
            return {
                'inbound': [],
                'outbound': [],
                'inventory': [],
                'payments': [],
                'receipts': [],
                'config': DEFAULT_CONFIG,
            }

def save_data(data):
    with data_lock:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# ============ 物料编码映射 ============
MATERIALS = {
    '6973555480693':'大我B13','6973555480891':'大我B7pro-C绿色','6973555480907':'大我B7pro-C白色',
    '6973555480884':'大我B7pro-C蓝色','6973555480730':'大我B6C黑色','6973555480761':'大我B6C绿色',
    '6973555480754':'大我B6C白色','6973555480709':'B531CS大我HiBreak-S-C白色',
    '6973555480792':'B651C大我HiBreak pro-C白色','6973555480808':'B651C大我HiBreak pro-C黑色',
    '6973555480938':'大我B10-C白色','6973555480600':'大我B1051c pro','6973555480815':'大我B751电容笔（C1）',
    '6974417015558':'国悦K3Color','BMA5B':'大我A5电磁笔','BMC7B':'大我C7电容笔',
    'BMCBX':'大我C1/C7系列笔芯','BMB5PT':'大我B5磁吸皮套','6973555481003':'HiBreak plus C白色',
    '6973555480778':'B531S大我HiBreak-S-BW白色','6973555480617':'B651大我HiBreak pro-BW白色',
    '6973555480679':'大我B7蓝色',
}
SAFETY = {'6973555480693':1,'6973555480884':3,'6973555480730':2,'6973555480709':2,'6973555480792':1}

def get_mat(code):
    d = load_data()
    mats = d.get('config', {}).get('materials', {})
    return mats.get(code, code)

def get_safety(code):
    return SAFETY.get(code, 1)

# ============ API: 配置管理 ============
@app.route('/api/config', methods=['GET'])
def api_config():
    s = require_auth()
    if not s: return jsonify({'error': '未登录'}), 401
    d = load_data()
    return jsonify(d.get('config', DEFAULT_CONFIG))

@app.route('/api/config/<section>', methods=['POST'])
def api_config_save(section):
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    d = load_data()
    if 'config' not in d: d['config'] = DEFAULT_CONFIG
    d['config'][section] = request.json
    save_data(d)
    return jsonify({'success': True})

# ============ API: 查询物料SN序列号 ============
@app.route('/api/sn/<code>', methods=['GET'])
def api_sn_lookup(code):
    s = require_auth()
    if not s: return jsonify({'error': '未登录'}), 401
    d = load_data()
    # 入库SN
    inbound_sns = []
    for r in d['inbound']:
        if r.get('code') == code:
            sns = [r.get('sn1'), r.get('sn2'), r.get('sn3')]
            sns = [sn for sn in sns if sn]
            if sns:
                inbound_sns.append({'no': r.get('no'), 'date': r.get('date'), 'sns': sns, 'qty': r.get('qty')})
    # 出库SN
    outbound_sns = []
    for r in d['outbound']:
        if r.get('code') == code:
            sn = r.get('snSerial')
            if sn:
                outbound_sns.append({'no': r.get('no'), 'date': r.get('date'), 'sn': sn, 'qty': r.get('qty'), 'customer': r.get('customer'), 'warehouse': r.get('warehouse')})
    
    # 当前库存SN（入库SN - 已出库SN）
    out_sn_set = {r['sn'] for r in outbound_sns}
    current_sns = []
    for r in inbound_sns:
        for sn in r['sns']:
            if sn not in out_sn_set:
                current_sns.append({'sn': sn, 'inNo': r['no'], 'inDate': r['date']})
    
    return jsonify({
        'code': code,
        'name': get_mat(code),
        'currentStockSns': current_sns,
        'inboundSns': inbound_sns,
        'outboundSns': outbound_sns,
    })

# ============ API: 登录 ============
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    user = USERS.get(username)
    if not user or (user['password'] and user['password'] != password):
        return jsonify({'success': False, 'error': '用户名或密码错误'})
    
    token = hashlib.sha256(f"{username}{time.time()}{random.random()}".encode()).hexdigest()
    sessions[token] = {'username': username, 'role': user['role'], 'name': user['name'], 'loginTime': datetime.now().isoformat()}
    
    return jsonify({'success': True, 'token': token, 'user': {'username': username, 'role': user['role'], 'name': user['name']}})

# 自动登录（免密码，默认登记员）
@app.route('/api/auto-login', methods=['POST'])
def api_auto_login():
    username = 'operator'
    user = USERS.get(username)
    token = hashlib.sha256(f"auto{time.time()}{random.random()}".encode()).hexdigest()
    sessions[token] = {'username': username, 'role': user['role'], 'name': user['name'], 'loginTime': datetime.now().isoformat()}
    return jsonify({'success': True, 'token': token, 'user': {'username': username, 'role': user['role'], 'name': user['name']}})

# 升级登录（登记员升级为管理员/财务）
@app.route('/api/upgrade', methods=['POST'])
def api_upgrade():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    user = USERS.get(username)
    if not user or (user['password'] and user['password'] != password):
        return jsonify({'success': False, 'error': '密码错误'})
    if user['role'] not in ('admin', 'finance'):
        return jsonify({'success': False, 'error': '该账号无管理员/财务权限'})
    
    token = hashlib.sha256(f"{username}{time.time()}{random.random()}".encode()).hexdigest()
    sessions[token] = {'username': username, 'role': user['role'], 'name': user['name'], 'loginTime': datetime.now().isoformat()}
    return jsonify({'success': True, 'token': token, 'user': {'username': username, 'role': user['role'], 'name': user['name']}})

# ============ API: 获取统计数据 ============
@app.route('/api/stats', methods=['GET'])
def api_stats():
    s = require_auth()
    if not s: return jsonify({'error': '未登录'}), 401
    
    d = load_data()
    inv = d['inventory']
    alerts = sum(1 for i in inv if i['stock'] <= get_safety(i['code']))
    return jsonify({
        'productCount': len(inv),
        'alertCount': alerts,
        'inboundCount': len(d['inbound']),
        'outboundCount': len(d['outbound']),
        'totalStock': sum(i['stock'] for i in inv),
    })

# ============ API: 入库 ============
@app.route('/api/inbound', methods=['GET', 'POST'])
def api_inbound():
    if request.method == 'GET':
        s = require_auth()
        if not s: return jsonify({'error': '未登录'}), 401
        d = load_data()
        return jsonify(d['inbound'])
    
    # POST - 新增入库
    s = require_auth()
    if not s: return jsonify({'error': '未登录'}), 401
    
    rec = request.json
    rec['operator'] = s['username']
    rec['time'] = datetime.now().isoformat()
    
    d = load_data()
    d['inbound'].append(rec)
    
    # 更新库存
    code = rec['code']
    name = rec.get('name') or get_mat(code)
    qty = float(rec.get('qty', 0))
    price = float(rec.get('price', 0))
    
    inv = d['inventory']
    item = next((i for i in inv if i['code'] == code), None)
    if not item:
        item = {'code': code, 'name': name, 'inQty': 0, 'inAmt': 0, 'outQty': 0, 'outAmt': 0, 'stock': 0}
        inv.append(item)
    item['name'] = name
    item['inQty'] += qty
    item['inAmt'] += qty * price
    item['stock'] = item['inQty'] - item['outQty']
    
    save_data(d)
    return jsonify({'success': True, 'record': rec})

# ============ API: 出库 ============
@app.route('/api/outbound', methods=['GET', 'POST'])
def api_outbound():
    if request.method == 'GET':
        s = require_auth()
        if not s: return jsonify({'error': '未登录'}), 401
        d = load_data()
        return jsonify(d['outbound'])
    
    # POST - 新增出库
    s = require_auth()
    if not s: return jsonify({'error': '未登录'}), 401
    
    rec = request.json
    rec['operator'] = s['username']
    rec['time'] = datetime.now().isoformat()
    
    d = load_data()
    
    # 检查库存
    code = rec['code']
    qty = float(rec.get('qty', 0))
    inv = d['inventory']
    item = next((i for i in inv if i['code'] == code), None)
    if item and qty > item['stock']:
        return jsonify({'success': False, 'error': f"库存不足！当前库存: {item['stock']}"})
    
    d['outbound'].append(rec)
    
    # 更新库存
    name = rec.get('materialName') or rec.get('name') or get_mat(code)
    price = float(rec.get('price', 0))
    
    if not item:
        item = {'code': code, 'name': name, 'inQty': 0, 'inAmt': 0, 'outQty': 0, 'outAmt': 0, 'stock': 0}
        inv.append(item)
    item['name'] = name
    item['outQty'] += qty
    item['outAmt'] += qty * price
    item['stock'] = item['inQty'] - item['outQty']
    
    save_data(d)
    return jsonify({'success': True, 'record': rec})

# ============ API: 批量出库（购物车模式） ============
@app.route('/api/outbound/batch', methods=['POST'])
def api_outbound_batch():
    s = require_role('admin', 'operator')
    if not s: return jsonify({'error': '无权限'}), 403
    
    data = request.json
    items = data.get('items', [])
    header = data.get('header', {})
    
    if not items:
        return jsonify({'success': False, 'error': '请添加出库商品'})
    
    d = load_data()
    batch_no = header.get('no') or ('DP' + datetime.now().strftime('%m%d%H%M%S') + str(random.randint(100,999)))
    date = header.get('date', datetime.now().strftime('%Y-%m-%d'))
    customer = header.get('customer', '')
    warehouse = header.get('warehouse', '')
    income_account = header.get('incomeAccount', '')
    operator = s['username']
    now = datetime.now().isoformat()
    
    records = []
    errors = []
    
    for item in items:
        code = item.get('code', '').strip()
        qty = float(item.get('qty', 0) or 0)
        price = float(item.get('price', 0) or 0)
        pprice = float(item.get('purchasePrice', 0) or 0)
        sn = item.get('snSerial', '').strip()
        name = item.get('materialName', '') or item.get('name', '') or get_mat(code)
        
        if not code: continue
        if qty <= 0: continue
        
        # 检查库存
        inv = d['inventory']
        stock_item = next((i for i in inv if i['code'] == code), None)
        if stock_item and qty > stock_item['stock']:
            errors.append(f'{name}: 库存不足(当前{stock_item["stock"]})')
            continue
        
        # 验证SN序列号（如果填写了SN）
        if sn:
            inbound_sns = set()
            for r in d['inbound']:
                if r.get('code') == code:
                    for sf in ['sn1', 'sn2', 'sn3']:
                        v = r.get(sf, '')
                        if v: inbound_sns.add(v)
            outbound_sns = set()
            for r in d['outbound']:
                if r.get('snSerial'): outbound_sns.add(r.get('snSerial'))
            if sn not in inbound_sns:
                errors.append(f'{name}: SN "{sn}" 不在入库记录中，无法出库')
                continue
            if sn in outbound_sns:
                errors.append(f'{name}: SN "{sn}" 已被出库，不能重复出库')
                continue
        
        rec = {
            'no': batch_no,
            'date': date,
            'code': code,
            'materialName': name,
            'qty': qty,
            'price': price,
            'amount': round(qty * price, 2),
            'purchasePrice': pprice,
            'incomeAccount': income_account,
            'warehouse': warehouse,
            'customer': customer,
            'snSerial': sn,
            'returnNo': item.get('returnNo', ''),
            'invoiceStatus': item.get('invoiceStatus', ''),
            'remark': item.get('remark', ''),
            'operator': operator,
            'time': now,
        }
        d['outbound'].append(rec)
        records.append(rec)
        
        # 更新库存
        if not stock_item:
            stock_item = {'code': code, 'name': name, 'inQty': 0, 'inAmt': 0, 'outQty': 0, 'outAmt': 0, 'stock': 0}
            inv.append(stock_item)
        stock_item['name'] = name
        stock_item['outQty'] += qty
        stock_item['outAmt'] += qty * price
        stock_item['stock'] = stock_item['inQty'] - stock_item['outQty']
    
    save_data(d)
    
    # WPS 同步（后台异步推送，不阻塞主流程）
    if WPS_SYNC_ENABLED and records:
        import threading
        def sync_wps():
            try:
                push_outbound_batch(records)
            except Exception as e:
                print(f'[WPS] 出库同步失败: {e}')
        threading.Thread(target=sync_wps, daemon=True).start()
    
    return jsonify({
        'success': len(errors) == 0,
        'batchNo': batch_no,
        'records': records,
        'errors': errors,
        'totalAmount': round(sum(r['amount'] for r in records), 2),
    })

# ============ API: 收付款登记 ============
@app.route('/api/payments', methods=['GET', 'POST'])
def api_payments():
    if request.method == 'GET':
        s = require_role('admin', 'finance')
        if not s: return jsonify({'error': '无权限'}), 403
        d = load_data()
        return jsonify(d.get('payments', []) + d.get('receipts', []))
    
    # POST
    s = require_role('admin', 'finance')
    if not s: return jsonify({'error': '无权限'}), 403
    
    rec = request.json
    rec['operator'] = s['username']
    rec['time'] = datetime.now().isoformat()
    
    d = load_data()
    ptype = rec.get('type', 'receipt')  # receipt收款 / payment付款
    if ptype == 'payment':
        if 'payments' not in d: d['payments'] = []
        d['payments'].append(rec)
    else:
        if 'receipts' not in d: d['receipts'] = []
        d['receipts'].append(rec)
    save_data(d)
    return jsonify({'success': True, 'record': rec})

# ============ API: 对账数据 ============
@app.route('/api/reconciliation', methods=['GET'])
def api_reconciliation():
    s = require_role('admin', 'finance')
    if not s: return jsonify({'error': '无权限'}), 403
    
    d = load_data()
    out_recs = d['outbound']
    receipts = d.get('receipts', [])
    payments = d.get('payments', [])
    
    # 按客户汇总应收
    customer_ar = {}
    for r in out_recs:
        cust = r.get('customer', '未知')
        if not cust: cust = '未知'
        amt = float(r.get('amount', 0) or 0)
        if cust not in customer_ar: customer_ar[cust] = {'sales': 0, 'received': 0}
        customer_ar[cust]['sales'] += amt
    
    for r in receipts:
        cust = r.get('customer', '')
        amt = float(r.get('amount', 0) or 0)
        if cust and cust in customer_ar:
            customer_ar[cust]['received'] += amt
    
    ar_list = []
    for cust, v in customer_ar.items():
        balance = round(v['sales'] - v['received'], 2)
        ar_list.append({'customer': cust, 'sales': round(v['sales'], 2), 'received': round(v['received'], 2), 'balance': balance, 'status': '已结清' if balance <= 0 else ('部分收款' if v['received'] > 0 else '未收款')})
    ar_list.sort(key=lambda x: x['balance'], reverse=True)
    
    # 按供应商汇总应付
    in_recs = d['inbound']
    supplier_ap = {}
    for r in in_recs:
        sup = r.get('supplier', '未知')
        if not sup: sup = '未知'
        amt = float(r.get('amount', 0) or 0)
        if sup not in supplier_ap: supplier_ap[sup] = {'purchase': 0, 'paid': 0}
        supplier_ap[sup]['purchase'] += amt
    
    for r in payments:
        sup = r.get('supplier', '')
        amt = float(r.get('amount', 0) or 0)
        if sup and sup in supplier_ap:
            supplier_ap[sup]['paid'] += amt
    
    ap_list = []
    for sup, v in supplier_ap.items():
        balance = round(v['purchase'] - v['paid'], 2)
        ap_list.append({'supplier': sup, 'purchase': round(v['purchase'], 2), 'paid': round(v['paid'], 2), 'balance': balance, 'status': '已结清' if balance <= 0 else ('部分付款' if v['paid'] > 0 else '未付款')})
    ap_list.sort(key=lambda x: x['balance'], reverse=True)
    
    total_ar = round(sum(a['balance'] for a in ar_list if a['balance'] > 0), 2)
    total_ap = round(sum(a['balance'] for a in ap_list if a['balance'] > 0), 2)
    total_receipts = round(sum(float(r.get('amount', 0) or 0) for r in receipts), 2)
    total_payments = round(sum(float(r.get('amount', 0) or 0) for r in payments), 2)
    
    return jsonify({
        'accountsReceivable': ar_list,
        'accountsPayable': ap_list,
        'summary': {
            'totalAR': total_ar,
            'totalAP': total_ap,
            'totalReceipts': total_receipts,
            'totalPayments': total_payments,
            'receiptCount': len(receipts),
            'paymentCount': len(payments),
        },
        'receipts': receipts,
        'payments': payments,
    })

# ============ API: 扫码SN反查产品 ============
@app.route('/api/sn-lookup/<sn>', methods=['GET'])
def api_sn_reverse_lookup(sn):
    s = require_auth()
    if not s: return jsonify({'error': '未登录'}), 401
    
    d = load_data()
    # 搜索入库记录中的SN
    for r in d['inbound']:
        sns = [r.get('sn1',''), r.get('sn2',''), r.get('sn3','')]
        if sn in sns:
            return jsonify({'found': True, 'code': r.get('code'), 'name': r.get('name'), 'inNo': r.get('no'), 'inDate': r.get('date')})
    
    # 搜索出库记录中的SN
    for r in d['outbound']:
        if r.get('snSerial') == sn:
            return jsonify({'found': True, 'code': r.get('code'), 'name': r.get('materialName'), 'outNo': r.get('no'), 'outDate': r.get('date')})
    
    return jsonify({'found': False})

# ============ API: 库存
@app.route('/api/inventory', methods=['GET'])
def api_inventory():
    s = require_auth()
    if not s: return jsonify({'error': '未登录'}), 401
    d = load_data()
    inv = d['inventory']
    result = []
    for i in inv:
        safety = get_safety(i['code'])
        stock = i['stock']
        if stock <= 0: alert = '缺货'
        elif stock <= safety: alert = '库存不足'
        elif stock > safety * 3: alert = '库存过多'
        else: alert = '正常'
        result.append({**i, 'safety': safety, 'alert': alert})
    return jsonify(result)

# ============ API: 资金汇总 ============
@app.route('/api/finance', methods=['GET'])
def api_finance():
    s = require_role('admin', 'finance')
    if not s: return jsonify({'error': '需要管理员或财务权限'}), 403
    
    d = load_data()
    out_recs = d['outbound']
    in_recs = d['inbound']
    
    now = datetime.now()
    
    # 支持时间段查询参数
    start_date = request.args.get('start', '')
    end_date = request.args.get('end', '')
    
    if start_date and end_date:
        out_recs = [r for r in out_recs if str(r.get('date', ''))[:10] >= start_date and str(r.get('date', ''))[:10] <= end_date]
        in_recs = [r for r in in_recs if str(r.get('date', ''))[:10] >= start_date and str(r.get('date', ''))[:10] <= end_date]
    
    def calc_stats(recs, date_field='date', amt_field='amount', cost_field=None):
        today = now.strftime('%Y-%m-%d')
        month = now.strftime('%Y-%m')
        year = now.strftime('%Y')
        
        day_amt = sum(float(r.get(amt_field, 0) or 0) for r in recs if str(r.get(date_field, ''))[:10] == today)
        month_amt = sum(float(r.get(amt_field, 0) or 0) for r in recs if str(r.get(date_field, ''))[:7] == month)
        year_amt = sum(float(r.get(amt_field, 0) or 0) for r in recs if str(r.get(date_field, ''))[:4] == year)
        total_amt = sum(float(r.get(amt_field, 0) or 0) for r in recs)
        
        day_cost = sum(float(r.get(cost_field, 0) or 0) * float(r.get('qty', 0) or 0) for r in recs if str(r.get(date_field, ''))[:10] == today) if cost_field else 0
        month_cost = sum(float(r.get(cost_field, 0) or 0) * float(r.get('qty', 0) or 0) for r in recs if str(r.get(date_field, ''))[:7] == month) if cost_field else 0
        year_cost = sum(float(r.get(cost_field, 0) or 0) * float(r.get('qty', 0) or 0) for r in recs if str(r.get(date_field, ''))[:4] == year) if cost_field else 0
        total_cost = sum(float(r.get(cost_field, 0) or 0) * float(r.get('qty', 0) or 0) for r in recs) if cost_field else 0
        
        return {
            'day': {'amount': round(day_amt, 2), 'cost': round(day_cost, 2), 'profit': round(day_amt - day_cost, 2)},
            'month': {'amount': round(month_amt, 2), 'cost': round(month_cost, 2), 'profit': round(month_amt - month_cost, 2)},
            'year': {'amount': round(year_amt, 2), 'cost': round(year_cost, 2), 'profit': round(year_amt - year_cost, 2)},
            'total': {'amount': round(total_amt, 2), 'cost': round(total_cost, 2), 'profit': round(total_amt - total_cost, 2)},
        }
    
    sales = calc_stats(out_recs, 'date', 'amount', 'purchasePrice')
    purchase = calc_stats(in_recs, 'date', 'amount')
    
    monthly = {}
    for r in out_recs:
        m = str(r.get('date', ''))[:7]
        if not m or len(m) < 7: continue
        amt = float(r.get('amount', 0) or 0)
        cost = float(r.get('purchasePrice', 0) or 0) * float(r.get('qty', 0) or 0)
        if m not in monthly: monthly[m] = {'sales': 0, 'cost': 0, 'count': 0}
        monthly[m]['sales'] += amt; monthly[m]['cost'] += cost; monthly[m]['count'] += 1
    
    monthly_list = [{'month': m, 'sales': round(v['sales'], 2), 'cost': round(v['cost'], 2), 'profit': round(v['sales'] - v['cost'], 2), 'count': v['count']} for m, v in sorted(monthly.items(), reverse=True)[:12]]
    
    customer_stats = {}
    for r in out_recs:
        cust = r.get('customer', '未知') or '未知'
        amt = float(r.get('amount', 0) or 0); cost = float(r.get('purchasePrice', 0) or 0) * float(r.get('qty', 0) or 0)
        if cust not in customer_stats: customer_stats[cust] = {'sales': 0, 'cost': 0, 'count': 0}
        customer_stats[cust]['sales'] += amt; customer_stats[cust]['cost'] += cost; customer_stats[cust]['count'] += 1
    
    customer_list = [{'name': k, 'sales': round(v['sales'], 2), 'cost': round(v['cost'], 2), 'profit': round(v['sales'] - v['cost'], 2), 'count': v['count']} for k, v in sorted(customer_stats.items(), key=lambda x: x[1]['sales'], reverse=True)]
    
    return jsonify({
        'sales': sales, 'purchase': purchase, 'monthly': monthly_list, 'customers': customer_list,
        'totalRecords': len(out_recs), 'totalInbound': len(in_recs),
        'queryStart': start_date, 'queryEnd': end_date,
    })

# ============ API: 导出 CSV ============
@app.route('/api/export/<data_type>', methods=['GET'])
def api_export(data_type):
    s = require_auth()
    if not s: return jsonify({'error': '未登录'}), 401
    
    d = load_data()
    if data_type == 'outbound':
        recs = d['outbound']
        csv = '单号,日期,物料编码,物料名称,数量,单价,金额,经办人,收入账户,仓位,客户,SN序列号,退货单号,发票情况,进货单价,备注\n'
        for r in recs:
            csv += f'"{r.get("no","")}","{r.get("date","")}","{r.get("code","")}","{r.get("materialName",r.get("name",""))}",{r.get("qty",0)},{r.get("price",0)},{r.get("amount",0)},"{r.get("operator","")}","{r.get("incomeAccount","")}","{r.get("warehouse","")}","{r.get("customer","")}","{r.get("snSerial","")}","{r.get("returnNo","")}","{r.get("invoiceStatus","")}",{r.get("purchasePrice",0)},"{r.get("remark","")}"\n'
    elif data_type == 'inbound':
        recs = d['inbound']
        csv = '单号,日期,物料编码,物料名称,数量,单价,金额,经办人,采购账户,入库仓位,供应商,SN1,SN2,SN3,备注\n'
        for r in recs:
            csv += f'"{r.get("no","")}","{r.get("date","")}","{r.get("code","")}","{r.get("name",r.get("materialName",""))}",{r.get("qty",0)},{r.get("price",0)},{r.get("amount",0)},"{r.get("operator","")}","{r.get("account","")}","{r.get("warehouse","")}","{r.get("supplier","")}","{r.get("sn1","")}","{r.get("sn2","")}","{r.get("sn3","")}","{r.get("remark","")}"\n'
    elif data_type == 'inventory':
        recs = d['inventory']
        csv = '物料编码,物料名称,入库数量,入库金额,出库数量,出库金额,库存,安全库存,状态\n'
        for i in recs:
            safety = get_safety(i['code'])
            stock = i['stock']
            alert = '缺货' if stock <= 0 else ('库存不足' if stock <= safety else '正常')
            csv += f'"{i["code"]}","{i["name"]}",{i["inQty"]},{i["inAmt"]},{i["outQty"]},{i["outAmt"]},{i["stock"]},{safety},{alert}\n'
    else:
        return jsonify({'error': '无效类型'}), 400
    
    from flask import Response
    return Response(csv, mimetype='text/csv', headers={'Content-Disposition': f'attachment;filename={data_type}.csv'})

# ============ API: 用户管理（管理员） ============
@app.route('/api/users', methods=['GET'])
def api_users():
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    return jsonify([{'username': k, 'role': v['role'], 'name': v['name']} for k, v in USERS.items()])

@app.route('/api/users', methods=['POST'])
def api_add_user():
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    data = request.json
    username = data.get('username', '').strip()
    role = data.get('role', 'operator')
    if not username or username in USERS:
        return jsonify({'success': False, 'error': '用户名已存在或无效'})
    if role not in ('admin', 'finance', 'operator'):
        return jsonify({'success': False, 'error': '无效角色'})
    USERS[username] = {'password': data.get('password', ''), 'role': role, 'name': data.get('name', username)}
    return jsonify({'success': True})

@app.route('/api/users/<username>', methods=['DELETE'])
def api_delete_user(username):
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    if username == 'admin' or username == '1':
        return jsonify({'success': False, 'error': '不能删除管理员'})
    if username in USERS:
        del USERS[username]
    return jsonify({'success': True})

@app.route('/api/users/<username>', methods=['PUT'])
def api_edit_user(username):
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    if username not in USERS:
        return jsonify({'success': False, 'error': '用户不存在'})
    data = request.json
    role = data.get('role', USERS[username]['role'])
    if role not in ('admin', 'finance', 'operator'):
        return jsonify({'success': False, 'error': '无效角色'})
    USERS[username]['role'] = role
    USERS[username]['name'] = data.get('name', USERS[username]['name'])
    if data.get('password'):
        USERS[username]['password'] = data['password']
    return jsonify({'success': True})

# ============ 静态文件 ============
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'inventory-web.html')

# ============ 健康检查（用于 Koyeb keep-alive） ============
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})

# ============ API: 退货登记 ============
@app.route('/api/outbound/<no>/return', methods=['POST'])
def api_outbound_return(no):
    s = require_role('admin', 'operator')
    if not s: return jsonify({'error': '无权限'}), 403
    
    data = request.json
    return_qty = float(data.get('qty', 0) or 0)
    return_reason = data.get('reason', '')
    
    if return_qty <= 0:
        return jsonify({'success': False, 'error': '退货数量必须大于0'})
    
    d = load_data()
    
    # 查找匹配的出库记录（同一单号的所有行）
    matched = [r for r in d['outbound'] if r.get('no') == no]
    if not matched:
        return jsonify({'success': False, 'error': '未找到出库记录'})
    
    # 对每行按比例退货
    total_qty = sum(float(r.get('qty', 0) or 0) for r in matched)
    now = datetime.now().isoformat()
    returned = []
    
    for r in matched:
        orig_qty = float(r.get('qty', 0) or 0)
        ratio = orig_qty / total_qty if total_qty > 0 else 0
        r_qty = round(return_qty * ratio, 2) if ratio > 0 else 0
        
        if r_qty <= 0: continue
        
        r['returnQty'] = float(r.get('returnQty', 0) or 0) + r_qty
        r['returnDate'] = now
        r['returnReason'] = return_reason
        
        # 恢复库存
        code = r.get('code')
        inv = d['inventory']
        item = next((i for i in inv if i['code'] == code), None)
        if item:
            item['outQty'] -= r_qty
            item['outAmt'] -= r_qty * float(r.get('price', 0) or 0)
            item['stock'] = item['inQty'] - item['outQty']
        
        returned.append({'code': code, 'name': r.get('materialName', ''), 'qty': r_qty, 'price': float(r.get('price', 0) or 0)})
    
    save_data(d)
    return jsonify({'success': True, 'returned': returned, 'totalReturnQty': return_qty, 'reason': return_reason})

# ============ API: 发票登记 ============
@app.route('/api/outbound/<no>/invoice', methods=['POST'])
def api_outbound_invoice(no):
    s = require_role('admin', 'finance')
    if not s: return jsonify({'error': '无权限'}), 403
    
    data = request.json
    invoice_no = data.get('invoiceNo', '')
    invoiced = data.get('invoiced', True)
    
    d = load_data()
    matched = [r for r in d['outbound'] if r.get('no') == no]
    if not matched:
        return jsonify({'success': False, 'error': '未找到出库记录'})
    
    now = datetime.now().isoformat()
    for r in matched:
        r['invoiced'] = invoiced
        r['invoiceNo'] = invoice_no
        r['invoiceDate'] = now
    
    save_data(d)
    return jsonify({'success': True, 'invoiceNo': invoice_no, 'invoiced': invoiced})

# ============ API: 发票库存统计 ============
@app.route('/api/invoice-stats', methods=['GET'])
def api_invoice_stats():
    s = require_role('admin', 'finance')
    if not s: return jsonify({'error': '无权限'}), 403
    
    d = load_data()
    out_recs = d['outbound']
    
    total = len(set(r.get('no') for r in out_recs if r.get('no')))
    invoiced = len(set(r.get('no') for r in out_recs if r.get('invoiced') and r.get('no')))
    not_invoiced = total - invoiced
    
    not_invoiced_list = []
    seen = set()
    for r in out_recs:
        no = r.get('no')
        if no and no not in seen and not r.get('invoiced'):
            amt = sum(float(r2.get('amount', 0) or 0) for r2 in out_recs if r2.get('no') == no)
            not_invoiced_list.append({'no': no, 'date': r.get('date'), 'customer': r.get('customer'), 'amount': round(amt, 2)})
            seen.add(no)
    
    return jsonify({
        'total': total,
        'invoiced': invoiced,
        'notInvoiced': not_invoiced,
        'notInvoicedList': not_invoiced_list[:20],
    })

# ============ API: WPS 同步管理 ============
@app.route('/api/sync/status', methods=['GET'])
def api_sync_status():
    """获取 WPS 同步状态"""
    s = require_auth()
    if not s: return jsonify({'error': '未登录'}), 401
    
    if not WPS_SYNC_ENABLED:
        return jsonify({'enabled': False, 'message': 'WPS 同步模块未安装'})
    
    status = get_sync_status()
    # 同时获取 WPS 端状态
    try:
        wps_status = get_wps_status()
        status['wps'] = wps_status
    except Exception as e:
        status['wps'] = {'error': str(e)}
    
    return jsonify(status)

@app.route('/api/sync/push', methods=['POST'])
def api_sync_push():
    """手动推送数据到 WPS"""
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    
    if not WPS_SYNC_ENABLED:
        return jsonify({'success': False, 'error': 'WPS 同步模块未安装'})
    
    data = request.json or {}
    push_type = data.get('type', 'all')  # all / outbound / inbound / inventory
    
    d = load_data()
    
    try:
        if push_type == 'outbound':
            result = push_outbound_batch(d.get('outbound', []))
        elif push_type == 'inbound':
            result = push_inbound_batch(d.get('inbound', []))
        elif push_type == 'inventory':
            result = push_inventory(d.get('inventory', []))
        else:
            result = full_push(d)
        
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/sync/pull', methods=['POST'])
def api_sync_pull():
    """从 WPS 拉取数据"""
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    
    if not WPS_SYNC_ENABLED:
        return jsonify({'success': False, 'error': 'WPS 同步模块未安装'})
    
    try:
        result = pull_all_sheets()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/sync/init', methods=['POST'])
def api_sync_init():
    """初始化 WPS Sheet 表头"""
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    
    if not WPS_SYNC_ENABLED:
        return jsonify({'success': False, 'error': 'WPS 同步模块未安装'})
    
    try:
        result = init_wps_sheets()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/sync/toggle', methods=['POST'])
def api_sync_toggle():
    """切换同步开关"""
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    
    if not WPS_SYNC_ENABLED:
        return jsonify({'success': False, 'error': 'WPS 同步模块未安装'})
    
    data = request.json or {}
    enabled = data.get('enabled', True)
    result = set_enabled(enabled)
    return jsonify(result)

@app.route('/api/sync/reset-errors', methods=['POST'])
def api_sync_reset_errors():
    """重置同步错误计数"""
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    
    if not WPS_SYNC_ENABLED:
        return jsonify({'success': False, 'error': 'WPS 同步模块未安装'})
    
    return jsonify(reset_errors())

@app.route('/api/sync/pull-all', methods=['POST'])
def api_sync_pull_all():
    """
    核心：从 WPS 拉取全部数据，替换本地 data.json
    WPS 是主数据源
    """
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    
    if not WPS_SYNC_ENABLED:
        return jsonify({'success': False, 'error': 'WPS 同步模块未安装'})
    
    try:
        result = pull_all_and_replace()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============ API: 仓位库存 ============
@app.route('/api/inventory/warehouse', methods=['GET'])
def api_inventory_warehouse():
    s = require_auth()
    if not s: return jsonify({'error': '未登录'}), 401
    
    d = load_data()
    out_recs = d['outbound']
    in_recs = d['inbound']
    
    # 收集所有仓位
    warehouses = set()
    for r in out_recs:
        wh = r.get('warehouse', '')
        if wh: warehouses.add(wh)
    for r in in_recs:
        wh = r.get('warehouse', '')
        if wh: warehouses.add(wh)
    
    # 按仓位统计库存
    wh_inventory = {}
    for wh in warehouses:
        wh_inventory[wh] = {'totalStock': 0, 'items': [], 'inQty': 0, 'outQty': 0}
    
    # 统计入库
    for r in in_recs:
        wh = r.get('warehouse', '') or '未指定'
        if wh not in wh_inventory:
            wh_inventory[wh] = {'totalStock': 0, 'items': [], 'inQty': 0, 'outQty': 0}
        code = r.get('code')
        qty = float(r.get('qty', 0) or 0)
        wh_inventory[wh]['inQty'] += qty
        item = next((i for i in wh_inventory[wh]['items'] if i['code'] == code), None)
        if not item:
            item = {'code': code, 'name': r.get('name', get_mat(code)), 'inQty': 0, 'outQty': 0, 'stock': 0}
            wh_inventory[wh]['items'].append(item)
        item['inQty'] += qty
    
    # 统计出库
    for r in out_recs:
        wh = r.get('warehouse', '') or '未指定'
        if wh not in wh_inventory:
            wh_inventory[wh] = {'totalStock': 0, 'items': [], 'inQty': 0, 'outQty': 0}
        code = r.get('code')
        qty = float(r.get('qty', 0) or 0) - float(r.get('returnQty', 0) or 0)
        wh_inventory[wh]['outQty'] += qty
        item = next((i for i in wh_inventory[wh]['items'] if i['code'] == code), None)
        if not item:
            item = {'code': code, 'name': r.get('materialName', get_mat(code)), 'inQty': 0, 'outQty': 0, 'stock': 0}
            wh_inventory[wh]['items'].append(item)
        item['outQty'] += qty
    
    result = []
    for wh, data in wh_inventory.items():
        for i in data['items']:
            i['stock'] = i['inQty'] - i['outQty']
            i['warehouse'] = wh
            if i['stock'] > 0 or i['inQty'] > 0:
                result.append(i)
    
    return jsonify(result)

# ============ API: 发票库存 ============
@app.route('/api/inventory/invoice', methods=['GET'])
def api_inventory_invoice():
    s = require_role('admin', 'finance')
    if not s: return jsonify({'error': '需要管理员或财务权限'}), 403
    
    d = load_data()
    out_recs = d['outbound']
    
    # 按物料编码统计发票情况
    invoice_stats = {}
    for r in out_recs:
        code = r.get('code')
        if not code: continue
        name = r.get('materialName', '') or get_mat(code)
        qty = float(r.get('qty', 0) or 0)
        return_qty = float(r.get('returnQty', 0) or 0)
        net_qty = qty - return_qty
        invoiced = r.get('invoiced', False)
        
        if code not in invoice_stats:
            invoice_stats[code] = {'code': code, 'name': name, 'totalQty': 0, 'invoicedQty': 0, 'notInvoicedQty': 0, 'invoicedNos': [], 'notInvoicedNos': []}
        
        invoice_stats[code]['totalQty'] += net_qty
        if invoiced:
            invoice_stats[code]['invoicedQty'] += net_qty
            if r.get('no') not in invoice_stats[code]['invoicedNos']:
                invoice_stats[code]['invoicedNos'].append(r.get('no'))
        else:
            invoice_stats[code]['notInvoicedQty'] += net_qty
            if r.get('no') not in invoice_stats[code]['notInvoicedNos']:
                invoice_stats[code]['notInvoicedNos'].append(r.get('no'))
    
    result = list(invoice_stats.values())
    result.sort(key=lambda x: x['notInvoicedQty'], reverse=True)
    
    return jsonify({
        'items': result,
        'totalInvoiced': sum(i['invoicedQty'] for i in result),
        'totalNotInvoiced': sum(i['notInvoicedQty'] for i in result),
        'totalItems': sum(i['totalQty'] for i in result),
    })

# ============ API: 收款状态更新 ============
@app.route('/api/outbound/<no>/payment', methods=['POST'])
def api_outbound_payment(no):
    s = require_role('admin', 'finance')
    if not s: return jsonify({'error': '需要管理员或财务权限'}), 403
    
    data = request.json
    paid = data.get('paid', False)
    paid_amount = float(data.get('paidAmount', 0) or 0)
    paid_date = data.get('paidDate', datetime.now().strftime('%Y-%m-%d %H:%M'))
    
    d = load_data()
    matched = [r for r in d['outbound'] if r.get('no') == no]
    if not matched:
        return jsonify({'success': False, 'error': '未找到出库记录'})
    
    for r in matched:
        r['paid'] = paid
        r['paidAmount'] = paid_amount if paid else 0
        r['paidDate'] = paid_date if paid else ''
    
    save_data(d)
    return jsonify({'success': True, 'paid': paid, 'paidAmount': paid_amount})

# ============ API: 调货登记 ============
@app.route('/api/transfer', methods=['GET', 'POST'])
def api_transfer():
    if request.method == 'GET':
        s = require_auth()
        if not s: return jsonify({'error': '未登录'}), 401
        d = load_data()
        return jsonify(d.get('transfers', []))
    
    # POST - 新增调货
    s = require_role('admin', 'operator')
    if not s: return jsonify({'error': '无权限'}), 403
    
    rec = request.json
    rec['operator'] = s['username']
    rec['time'] = datetime.now().isoformat()
    
    d = load_data()
    if 'transfers' not in d:
        d['transfers'] = []
    
    code = rec.get('code', '')
    qty = float(rec.get('qty', 0) or 0)
    name = rec.get('name', '') or get_mat(code)
    
    if not code or qty <= 0:
        return jsonify({'success': False, 'error': '请填写物料编码和数量'})
    
    # 检查调出仓位库存
    from_wh = rec.get('fromWarehouse', '')
    to_wh = rec.get('toWarehouse', '')
    
    # 统计调出仓位该商品库存
    in_qty = sum(float(r.get('qty', 0) or 0) for r in d['inbound'] if r.get('code') == code and r.get('warehouse') == from_wh)
    out_qty = sum(float(r.get('qty', 0) or 0) for r in d['outbound'] if r.get('code') == code and r.get('warehouse') == from_wh)
    stock = in_qty - out_qty
    
    if stock < qty:
        return jsonify({'success': False, 'error': f'{from_wh}库存不足！当前库存: {stock}'})
    
    d['transfers'].append(rec)
    
    # 更新库存：在出库表中加一条（调出仓），在入库表中加一条（调入仓）
    now = datetime.now().isoformat()
    
    out_rec = {
        'no': 'TF-OUT-' + rec.get('no', ''),
        'date': rec.get('date', ''),
        'code': code,
        'materialName': name,
        'qty': qty,
        'price': 0,
        'amount': 0,
        'warehouse': from_wh,
        'customer': f'调货至{to_wh}',
        'operator': s['username'],
        'time': now,
        'snSerial': f'调货_{rec.get("no","")}',
        'remark': rec.get('remark', ''),
    }
    in_rec = {
        'no': 'TF-IN-' + rec.get('no', ''),
        'date': rec.get('date', ''),
        'code': code,
        'name': name,
        'qty': qty,
        'price': 0,
        'amount': 0,
        'warehouse': to_wh,
        'supplier': f'调货来自{from_wh}',
        'operator': s['username'],
        'time': now,
        'sn1': f'调货_{rec.get("no","")}',
        'remark': rec.get('remark', ''),
    }
    d['outbound'].append(out_rec)
    d['inbound'].append(in_rec)
    
    # 更新 inventory
    inv = d['inventory']
    item = next((i for i in inv if i['code'] == code), None)
    if not item:
        item = {'code': code, 'name': name, 'inQty': 0, 'inAmt': 0, 'outQty': 0, 'outAmt': 0, 'stock': 0}
        inv.append(item)
    item['name'] = name
    item['inQty'] += qty
    item['outQty'] += qty
    # stock 不变（一进一出）
    item['stock'] = item['inQty'] - item['outQty']
    
    save_data(d)
    return jsonify({'success': True, 'record': rec})

# ============ API: 编辑/删除记录（管理员） ============
@app.route('/api/outbound/<no>', methods=['PUT', 'DELETE'])
def api_outbound_modify(no):
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    
    d = load_data()
    
    if request.method == 'DELETE':
        # 删除整单，恢复库存
        matched = [r for r in d['outbound'] if r.get('no') == no]
        inv = d['inventory']
        for r in matched:
            code = r.get('code')
            qty = float(r.get('qty', 0) or 0)
            price = float(r.get('price', 0) or 0)
            item = next((i for i in inv if i['code'] == code), None)
            if item:
                item['outQty'] -= qty
                item['outAmt'] -= qty * price
                item['stock'] = item['inQty'] - item['outQty']
        d['outbound'] = [r for r in d['outbound'] if r.get('no') != no]
        save_data(d)
        return jsonify({'success': True, 'deleted': len(matched)})
    
    # PUT - 更新
    data = request.json
    for r in d['outbound']:
        if r.get('no') == no:
            for k, v in data.items():
                r[k] = v
    save_data(d)
    return jsonify({'success': True})

@app.route('/api/inbound/<no>', methods=['PUT', 'DELETE'])
def api_inbound_modify(no):
    s = require_admin()
    if not s: return jsonify({'error': '需要管理员权限'}), 403
    
    d = load_data()
    
    if request.method == 'DELETE':
        matched = [r for r in d['inbound'] if r.get('no') == no]
        inv = d['inventory']
        for r in matched:
            code = r.get('code')
            qty = float(r.get('qty', 0) or 0)
            price = float(r.get('price', 0) or 0)
            item = next((i for i in inv if i['code'] == code), None)
            if item:
                item['inQty'] -= qty
                item['inAmt'] -= qty * price
                item['stock'] = item['inQty'] - item['outQty']
        d['inbound'] = [r for r in d['inbound'] if r.get('no') != no]
        save_data(d)
        return jsonify({'success': True, 'deleted': len(matched)})
    
    data = request.json
    for r in d['inbound']:
        if r.get('no') == no:
            for k, v in data.items():
                r[k] = v
    save_data(d)
    return jsonify({'success': True})

# ============ API: 批量入库（购物车模式） ============
@app.route('/api/inbound/batch', methods=['POST'])
def api_inbound_batch():
    s = require_role('admin', 'operator')
    if not s: return jsonify({'error': '无权限'}), 403
    
    data = request.json
    items = data.get('items', [])
    header = data.get('header', {})
    
    if not items:
        return jsonify({'success': False, 'error': '请添加入库商品'})
    
    d = load_data()
    batch_no = header.get('no') or ('A' + datetime.now().strftime('%m%d%H%M') + str(random.randint(10,99)))
    date = header.get('date', datetime.now().strftime('%Y-%m-%d %H:%M'))
    account = header.get('account', '')
    warehouse = header.get('warehouse', '')
    supplier = header.get('supplier', '')
    operator = s['username']
    now = datetime.now().isoformat()
    
    records = []
    
    for item in items:
        code = item.get('code', '').strip()
        qty = float(item.get('qty', 0) or 0)
        price = float(item.get('price', 0) or 0)
        name = item.get('name', '') or item.get('materialName', '') or get_mat(code)
        sn1 = item.get('sn1', '')
        sn2 = item.get('sn2', '')
        sn3 = item.get('sn3', '')
        
        if not code or qty <= 0: continue
        
        rec = {
            'no': batch_no, 'date': date, 'code': code, 'name': name,
            'qty': qty, 'price': price, 'amount': round(qty * price, 2),
            'account': account, 'warehouse': warehouse, 'supplier': supplier,
            'sn1': sn1, 'sn2': sn2, 'sn3': sn3,
            'remark': item.get('remark', ''),
            'operator': operator, 'time': now,
        }
        d['inbound'].append(rec)
        records.append(rec)
        
        inv = d['inventory']
        stock_item = next((i for i in inv if i['code'] == code), None)
        if not stock_item:
            stock_item = {'code': code, 'name': name, 'inQty': 0, 'inAmt': 0, 'outQty': 0, 'outAmt': 0, 'stock': 0}
            inv.append(stock_item)
        stock_item['name'] = name
        stock_item['inQty'] += qty
        stock_item['inAmt'] += qty * price
        stock_item['stock'] = stock_item['inQty'] - stock_item['outQty']
    
    save_data(d)
    
    # WPS 同步（后台异步推送）
    if WPS_SYNC_ENABLED and records:
        import threading
        def sync_wps():
            try:
                push_inbound_batch(records)
            except Exception as e:
                print(f'[WPS] 入库同步失败: {e}')
        threading.Thread(target=sync_wps, daemon=True).start()
    
    return jsonify({'success': True, 'batchNo': batch_no, 'records': records, 'totalAmount': round(sum(r['amount'] for r in records), 2)})

# ============ 启动
if __name__ == '__main__':
    # 初始化数据文件
    if not os.path.exists(DATA_FILE):
        init_data = {
            'inbound': [
                {'no':'A0001','date':'2026-04-19','code':'6973555480730','name':'大我B6C黑色','qty':3,'price':950,'amount':2850,'account':'广东北斗','warehouse':'广州百脑汇仓','supplier':'深圳大我','sn1':'B6CLR0B2FMIB006000345','sn2':'B6CLR0B2FNOA006000226','sn3':'B6CLR0B2FMNA006000271','operator':'admin','time':datetime.now().isoformat()},
                {'no':'A0001','date':'2026-04-19','code':'6973555480884','name':'大我B7pro-C蓝色','qty':3,'price':1960,'amount':5880,'account':'广东北斗','warehouse':'广州百脑汇仓','supplier':'深圳大我','sn1':'B7CPR0L2GD1A007000227','sn2':'B7CPR0L2GD1A007000224','sn3':'B7CPR0L2GD1A007000328','operator':'admin','time':datetime.now().isoformat()},
                {'no':'A0001','date':'2026-04-19','code':'6973555480693','name':'大我B13','qty':1,'price':3500,'amount':3500,'account':'广东北斗','warehouse':'深圳大我仓','supplier':'深圳大我','sn1':'B13CA0W2FMIA002000006','operator':'admin','time':datetime.now().isoformat()},
                {'no':'A0001','date':'2026-04-19','code':'6973555480792','name':'B651C大我HiBreak pro-C白色','qty':2,'price':2400,'amount':4800,'account':'广东北斗','warehouse':'广州百脑汇仓','supplier':'深圳大我','sn1':'B651CNW2FNLD006000336','sn2':'B651CNW2FN9E006000711','operator':'admin','time':datetime.now().isoformat()},
            ],
            'outbound': [
                {'no':'DP0419123307456','date':'2026-04-19','code':'6973555480730','materialName':'大我B6C黑色','qty':1,'price':1017,'amount':1017,'purchasePrice':950,'incomeAccount':'广州彩次元','warehouse':'广州百脑汇仓','customer':'PDD彩次元','snSerial':'B6CLR0B2FMNA006000271','operator':'admin','time':datetime.now().isoformat()},
                {'no':'DP0420091528347','date':'2026-04-20','code':'6973555480792','materialName':'B651C大我HiBreak pro-C白色','qty':1,'price':2829,'amount':2829,'purchasePrice':2400,'incomeAccount':'广州彩次元','warehouse':'广州百脑汇仓','customer':'PDD彩次元','snSerial':'B651CNW2FN9E006000711','operator':'admin','time':datetime.now().isoformat()},
                {'no':'DP0421153045128','date':'2026-04-21','code':'6973555480884','materialName':'大我B7pro-C蓝色','qty':1,'price':2199,'amount':2199,'purchasePrice':1960,'incomeAccount':'广州彩次元','warehouse':'广州百脑汇仓','customer':'PDD彩次元','snSerial':'B7CPR0L2GD1A007000436','operator':'operator','time':datetime.now().isoformat()},
            ],
            'inventory': [],
            'payments': [],
            'receipts': [],
        }
        # 初始化库存
        for r in init_data['inbound']:
            code, name, qty, price = r['code'], r['name'], r['qty'], r['price']
            item = next((i for i in init_data['inventory'] if i['code'] == code), None)
            if not item:
                item = {'code': code, 'name': name, 'inQty': 0, 'inAmt': 0, 'outQty': 0, 'outAmt': 0, 'stock': 0}
                init_data['inventory'].append(item)
            item['inQty'] += qty
            item['inAmt'] += qty * price
        for r in init_data['outbound']:
            code, name, qty, price = r['code'], r.get('materialName', r.get('name', '')), r['qty'], r['price']
            item = next((i for i in init_data['inventory'] if i['code'] == code), None)
            if not item:
                item = {'code': code, 'name': name, 'inQty': 0, 'inAmt': 0, 'outQty': 0, 'outAmt': 0, 'stock': 0}
                init_data['inventory'].append(item)
            item['outQty'] += qty
            item['outAmt'] += qty * price
        for i in init_data['inventory']:
            i['stock'] = i['inQty'] - i['outQty']
        save_data(init_data)
    
    # WPS 同步在 PythonAnywhere 免费版不可用（网络限制），跳过
    port = int(os.environ.get('PORT', 8001))
    print(f'🚀 出入库管理系统后端已启动: http://0.0.0.0:{port}')
    app.run(host='0.0.0.0', port=port, debug=False)
