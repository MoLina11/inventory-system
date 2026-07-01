"""
WPS 智能表格数据同步模块 — WPS 为主数据源
通过 AirScript 2.0 API 实现 PythonAnywhere 后端与 WPS 智能表格的实时双向同步

架构：WPS 智能表格 ↔ AirScript 2.0 API ↔ server.py ↔ data.json ↔ 前端

注意：智能表格 AirScript 单次超时 5 秒，需小批量同步（每批 10-20 条）
"""
import json, os, time, logging, threading, urllib.request, urllib.error
from datetime import datetime

# ============ 配置 ============
# TODO: 用户创建智能表格后更新 webhook
AIRSCRIPT_WEBHOOK = 'https://www.kdocs.cn/api/v3/ide/file/PLACEHOLDER/script/PLACEHOLDER/sync_task'
AIRSCRIPT_TOKEN = '4ixlDYFLLEks11xViYVoOf'
SHEET_OUTBOUND = '销售出库明细表'
SHEET_INBOUND = '进货入库明细表'
SHEET_INVENTORY = '库存统计表'
BATCH_SIZE = 20  # 智能表格 5 秒超时，每批 20 条

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
logger = logging.getLogger('wps_sync')

_sync_status = {
    'enabled': True, 'last_push': None, 'last_pull': None,
    'push_errors': 0, 'pull_errors': 0, 'last_error': None,
    'source': 'wps',  # 'wps' = WPS 是主数据源
}
_status_lock = threading.Lock()

# ============ 底层 API 调用 ============
def _call_airscript(action, sheet=None, rows=None, max_rows=None, timeout=120):
    argv = {'action': action}
    if sheet: argv['sheet'] = sheet
    if rows is not None: argv['rows'] = rows
    if max_rows is not None: argv['maxRows'] = max_rows
    payload = json.dumps({'Context': {'argv': argv}}).encode('utf-8')
    hdrs = {'Content-Type': 'application/json', 'AirScript-Token': AIRSCRIPT_TOKEN}
    req = urllib.request.Request(AIRSCRIPT_WEBHOOK, payload, hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise Exception(f'API HTTP {e.code}: {e.read().decode("utf-8", errors="replace")[:300]}')
    except Exception as e:
        raise Exception(f'API 调用失败: {e}')
    if data.get('error'):
        raise Exception(f'脚本错误: {data["error"]}')
    result = data.get('data', {}).get('result', '')
    if isinstance(result, str):
        try: result = json.loads(result)
        except: result = None if result == '[Undefined]' else {'raw': result}
    return result

def _update_status(k, v):
    with _status_lock: _sync_status[k] = v

def _inc_err(push=True):
    with _status_lock:
        if push: _sync_status['push_errors'] += 1
        else: _sync_status['pull_errors'] += 1

# ============ 推送（系统 → WPS）============
def push_outbound_record(record):
    if not _sync_status['enabled']: return {'success': False, 'message': '同步已禁用'}
    try:
        row = ['', record.get('no',''), record.get('date',''), record.get('code',''),
               record.get('materialName',''), str(record.get('qty',0)), str(record.get('price',0)),
               str(record.get('amount',0)), record.get('operator',''), record.get('incomeAccount',''),
               record.get('warehouse',''), record.get('customer',''), record.get('snSerial',''),
               record.get('returnNo',''), record.get('invoiceStatus',''),
               str(record.get('purchasePrice',0)), record.get('remark','')]
        _call_airscript('append', sheet=SHEET_OUTBOUND, rows=[row])
        _update_status('last_push', datetime.now().isoformat())
        return {'success': True, 'message': '推送成功'}
    except Exception as e:
        _inc_err(True); _update_status('last_error', str(e))
        return {'success': False, 'message': str(e)}

def push_inbound_record(record):
    if not _sync_status['enabled']: return {'success': False, 'message': '同步已禁用'}
    try:
        row = ['', record.get('no',''), record.get('date',''), record.get('code',''),
               record.get('name',''), str(record.get('qty',0)), str(record.get('price',0)),
               str(record.get('amount',0)), record.get('operator',''), record.get('account',''),
               record.get('warehouse',''), record.get('supplier',''),
               record.get('sn1',''), record.get('sn2',''), record.get('sn3',''), record.get('remark','')]
        _call_airscript('append', sheet=SHEET_INBOUND, rows=[row])
        _update_status('last_push', datetime.now().isoformat())
        return {'success': True, 'message': '推送成功'}
    except Exception as e:
        _inc_err(True); _update_status('last_error', str(e))
        return {'success': False, 'message': str(e)}

def push_outbound_batch(records):
    if not _sync_status['enabled'] or not records: return {'success': True, 'count': len(records) if records else 0}
    try:
        rows = []
        for r in records:
            rows.append(['', r.get('no',''), r.get('date',''), r.get('code',''),
                r.get('materialName',''), str(r.get('qty',0)), str(r.get('price',0)),
                str(r.get('amount',0)), r.get('operator',''), r.get('incomeAccount',''),
                r.get('warehouse',''), r.get('customer',''), r.get('snSerial',''),
                r.get('returnNo',''), r.get('invoiceStatus',''), str(r.get('purchasePrice',0)), r.get('remark','')])
        for i in range(0, len(rows), BATCH_SIZE):
            _call_airscript('append', sheet=SHEET_OUTBOUND, rows=rows[i:i+BATCH_SIZE], timeout=30)
        _update_status('last_push', datetime.now().isoformat())
        return {'success': True, 'count': len(rows)}
    except Exception as e:
        _inc_err(True); _update_status('last_error', str(e))
        return {'success': False, 'message': str(e)}

def push_inbound_batch(records):
    if not _sync_status['enabled'] or not records: return {'success': True, 'count': len(records) if records else 0}
    try:
        rows = []
        for r in records:
            rows.append(['', r.get('no',''), r.get('date',''), r.get('code',''),
                r.get('name',''), str(r.get('qty',0)), str(r.get('price',0)),
                str(r.get('amount',0)), r.get('operator',''), r.get('account',''),
                r.get('warehouse',''), r.get('supplier',''),
                r.get('sn1',''), r.get('sn2',''), r.get('sn3',''), r.get('remark','')])
        for i in range(0, len(rows), BATCH_SIZE):
            _call_airscript('append', sheet=SHEET_INBOUND, rows=rows[i:i+BATCH_SIZE], timeout=30)
        _update_status('last_push', datetime.now().isoformat())
        return {'success': True, 'count': len(rows)}
    except Exception as e:
        _inc_err(True); _update_status('last_error', str(e))
        return {'success': False, 'message': str(e)}

def push_inventory(inventory_data):
    if not _sync_status['enabled']: return {'success': False}
    try:
        rows = []
        for item in inventory_data:
            rows.append([item.get('code',''), item.get('name',''),
                str(item.get('inQty',0)), str(item.get('inAmt',0)),
                str(item.get('outQty',0)), str(item.get('outAmt',0)),
                str(item.get('stock',0)), str(item.get('safety',1)),
                item.get('alert','正常'), ''])
        _call_airscript('write_all', sheet=SHEET_INVENTORY, rows=rows, timeout=180)
        _update_status('last_push', datetime.now().isoformat())
        return {'success': True, 'count': len(rows)}
    except Exception as e:
        _inc_err(True); _update_status('last_error', str(e))
        return {'success': False, 'message': str(e)}

# ============ 拉取（WPS → 系统）============
def pull_sheet(sheet_name, max_rows=1000):
    try:
        result = _call_airscript('read', sheet=sheet_name, max_rows=max_rows, timeout=180)
        _update_status('last_pull', datetime.now().isoformat())
        if result is None: return {'success': True, 'headers': [], 'rows': [], 'rowCount': 0}
        return {'success': True, 'headers': result.get('headers',[]), 'rows': result.get('rows',[]),
                'rowCount': result.get('rowCount',0), 'readCount': result.get('readCount',0),
                'truncated': result.get('truncated', False)}
    except Exception as e:
        _inc_err(False); _update_status('last_error', str(e))
        return {'success': False, 'message': str(e)}

def pull_all_sheets():
    results = {}
    for name, label in [('outbound', SHEET_OUTBOUND), ('inbound', SHEET_INBOUND), ('inventory', SHEET_INVENTORY)]:
        results[name] = pull_sheet(label)
    return results

# ============ 核心：从 WPS 拉取数据替换本地 data.json ============
def pull_all_and_replace():
    """
    从 WPS 拉取全部数据，替换本地 data.json。
    WPS 是主数据源，本操作会覆盖系统本地数据。
    
    Returns:
        dict: 包含各 Sheet 的数据统计
    """
    results = {'outbound': 0, 'inbound': 0, 'inventory': 0, 'success': False, 'errors': []}
    
    # 1. 拉取出库数据
    ob = pull_sheet(SHEET_OUTBOUND, max_rows=2000)
    ob_records = []
    if ob.get('success') and ob.get('rows'):
        headers = ob['headers']
        for row in ob['rows']:
            rec = _parse_outbound_row(row, headers)
            if rec: ob_records.append(rec)
        results['outbound'] = len(ob_records)
    elif not ob.get('success'):
        results['errors'].append(f'出库: {ob.get("message")}')
    
    # 2. 拉取入库数据
    ib = pull_sheet(SHEET_INBOUND, max_rows=2000)
    ib_records = []
    if ib.get('success') and ib.get('rows'):
        headers = ib['headers']
        for row in ib['rows']:
            rec = _parse_inbound_row(row, headers)
            if rec: ib_records.append(rec)
        results['inbound'] = len(ib_records)
    elif not ib.get('success'):
        results['errors'].append(f'入库: {ib.get("message")}')
    
    # 3. 拉取库存数据
    inv = pull_sheet(SHEET_INVENTORY, max_rows=500)
    inv_records = []
    if inv.get('success') and inv.get('rows'):
        headers = inv['headers']
        for row in inv['rows']:
            rec = _parse_inventory_row(row, headers)
            if rec: inv_records.append(rec)
        results['inventory'] = len(inv_records)
    elif not inv.get('success'):
        results['errors'].append(f'库存: {inv.get("message")}')
    
    # 4. 读取现有 data.json 保留 config、users 等非出入库数据
    existing = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except: pass
    
    # 5. 构建新数据（保留 config/payments/receipts/transfers，替换 inbound/outbound/inventory）
    new_data = {
        'inbound': ib_records,
        'outbound': ob_records,
        'inventory': inv_records,
        'config': existing.get('config', {}),
        'payments': existing.get('payments', []),
        'receipts': existing.get('receipts', []),
        'transfers': existing.get('transfers', []),
    }
    
    # 6. 写入 data.json
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        results['success'] = True
        _update_status('last_pull', datetime.now().isoformat())
        logger.info(f'WPS 主数据同步完成: 出库{len(ob_records)} 入库{len(ib_records)} 库存{len(inv_records)}')
    except Exception as e:
        results['errors'].append(f'写入 data.json 失败: {e}')
    
    return results

def _parse_outbound_row(row, headers):
    """将 WPS 出库行数据解��为系统记录格式"""
    if len(row) < 2:
        return None
    rec = {
        'no': str(row[1]) if len(row) > 1 else '',
        'date': str(row[2]) if len(row) > 2 else '',
        'code': str(row[3]) if len(row) > 3 else '',
        'materialName': str(row[4]) if len(row) > 4 else '',
        'qty': _to_float(row[5]) if len(row) > 5 else 0,
        'price': _to_float(row[6]) if len(row) > 6 else 0,
        'amount': _to_float(row[7]) if len(row) > 7 else 0,
        'operator': str(row[8]) if len(row) > 8 else '',
        'incomeAccount': str(row[9]) if len(row) > 9 else '',
        'warehouse': str(row[10]) if len(row) > 10 else '',
        'customer': str(row[11]) if len(row) > 11 else '',
        'snSerial': str(row[12]) if len(row) > 12 else '',
        'returnNo': str(row[13]) if len(row) > 13 else '',
        'invoiceStatus': str(row[14]) if len(row) > 14 else '',
        'purchasePrice': _to_float(row[15]) if len(row) > 15 else 0,
        'remark': str(row[16]) if len(row) > 16 else '',
        'time': datetime.now().isoformat(),
    }
    if not rec.get('no') or rec['no'] in ('单号', '出库单号', '序号', ''):
        return None
    return rec

def _parse_inbound_row(row, headers):
    """将 WPS 入库行数据解析为系统记录格式"""
    if len(row) < 2:
        return None
    rec = {
        'no': str(row[1]) if len(row) > 1 else '',
        'date': str(row[2]) if len(row) > 2 else '',
        'code': str(row[3]) if len(row) > 3 else '',
        'name': str(row[4]) if len(row) > 4 else '',
        'qty': _to_float(row[5]) if len(row) > 5 else 0,
        'price': _to_float(row[6]) if len(row) > 6 else 0,
        'amount': _to_float(row[7]) if len(row) > 7 else 0,
        'operator': str(row[8]) if len(row) > 8 else '',
        'account': str(row[9]) if len(row) > 9 else '',
        'warehouse': str(row[10]) if len(row) > 10 else '',
        'supplier': str(row[11]) if len(row) > 11 else '',
        'sn1': str(row[12]) if len(row) > 12 else '',
        'sn2': str(row[13]) if len(row) > 13 else '',
        'sn3': str(row[14]) if len(row) > 14 else '',
        'remark': str(row[15]) if len(row) > 15 else '',
        'time': datetime.now().isoformat(),
    }
    if not rec.get('no') or rec['no'] in ('单号', '入库单号', '序号', ''):
        return None
    return rec

def _parse_inventory_row(row, headers):
    """将 WPS 库存行数据解析为系统记录格式"""
    if len(row) >= 7:
        code = str(row[0]) if len(row) > 0 else ''
        if not code or code in ('物料编码', '编码', ''): return None
        return {
            'code': code,
            'name': str(row[1]) if len(row) > 1 else '',
            'inQty': _to_float(row[2]) if len(row) > 2 else 0,
            'inAmt': _to_float(row[3]) if len(row) > 3 else 0,
            'outQty': _to_float(row[4]) if len(row) > 4 else 0,
            'outAmt': _to_float(row[5]) if len(row) > 5 else 0,
            'stock': _to_float(row[6]) if len(row) > 6 else 0,
            'safety': _to_float(row[7]) if len(row) > 7 else 1,
            'alert': str(row[8]) if len(row) > 8 else '正常',
        }

def _to_float(v):
    try: return float(v)
    except: return 0.0

# ============ 状态 ============
def get_status():
    with _status_lock: return dict(_sync_status)

def set_enabled(enabled):
    _update_status('enabled', bool(enabled))
    return {'success': True, 'enabled': bool(enabled)}

def reset_errors():
    with _status_lock:
        _sync_status['push_errors'] = 0
        _sync_status['pull_errors'] = 0
        _sync_status['last_error'] = None
    return {'success': True}

def full_push(data):
    results = {}
    if data.get('outbound'): results['outbound'] = push_outbound_batch(data['outbound'])
    if data.get('inbound'): results['inbound'] = push_inbound_batch(data['inbound'])
    if data.get('inventory'): results['inventory'] = push_inventory(data['inventory'])
    _update_status('last_push', datetime.now().isoformat())
    return results

def init_wps_sheets():
    try:
        _call_airscript('init', timeout=120)
        return {'success': True}
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_wps_status():
    try:
        result = _call_airscript('status', timeout=60)
        return {'success': True, 'result': result}
    except Exception as e:
        return {'success': False, 'message': str(e)}
