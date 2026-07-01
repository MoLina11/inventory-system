"""
WPS 智能表格数据同步模块 — 工作表 API
通过 AirScript 1.0 的 Cells API 实现 Web 系统与智能表格的双向同步
"""
import json, os, logging, threading, urllib.request, urllib.error
from datetime import datetime

AIRSCRIPT_WEBHOOK = 'https://www.kdocs.cn/api/v3/ide/file/cuCCqjRY0r2N/script/V2-5OP8Jlz20PGcPPpCDuVW9j/sync_task'
AIRSCRIPT_TOKEN = '4ixlDYFLLEks11xViYVoOf'

SHEET_OUTBOUND = '出库记录'
SHEET_INBOUND = '入库记录'
SHEET_INVENTORY = '库存汇总'

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
logger = logging.getLogger('wps_sync')

_sync_status = {
    'enabled': True, 'last_push': None, 'last_pull': None,
    'push_errors': 0, 'pull_errors': 0, 'last_error': None,
}
_status_lock = threading.Lock()

def _call(action, sheet, **kwargs):
    argv = {'action': action, 'sheet': sheet}
    argv.update(kwargs)
    payload = json.dumps({'Context': {'argv': argv}}).encode('utf-8')
    hdrs = {'Content-Type': 'application/json', 'AirScript-Token': AIRSCRIPT_TOKEN}
    req = urllib.request.Request(AIRSCRIPT_WEBHOOK, payload, hdrs)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        raise Exception(f'API 调用失败: {e}')
    if data.get('error'):
        raise Exception(f'脚本错误: {data["error"]}')
    result = data.get('data', {}).get('result', '')
    if isinstance(result, str):
        try: result = json.loads(result)
        except: result = None if result == '[Undefined]' else {'raw': result}
    return result

def _update(k, v):
    with _status_lock: _sync_status[k] = v

def _err(push=True):
    with _status_lock:
        if push: _sync_status['push_errors'] += 1
        else: _sync_status['pull_errors'] += 1

# ============ 推送（系统 → 智能表格）============
def _get_next_row(sheet_name):
    """获取下一个空行"""
    r = _call('readRows', sheet_name, startRow=1, endRow=5000, cols=1)
    if r and r.get('success'):
        return len(r.get('data', [])) + 1
    return 2

def push_outbound_record(record):
    if not _sync_status['enabled']: return {'success': False}
    try:
        row = _get_next_row(SHEET_OUTBOUND)
        data = [
            str(row - 1), record.get('no', ''), record.get('date', ''),
            record.get('code', ''), record.get('materialName', ''),
            str(record.get('qty', 0)), str(record.get('price', 0)),
            str(record.get('amount', 0)), record.get('operator', ''),
            record.get('incomeAccount', ''), record.get('warehouse', ''),
            record.get('customer', ''), record.get('snSerial', ''),
            record.get('returnNo', ''), record.get('invoiceStatus', ''),
            str(record.get('purchasePrice', 0)), record.get('remark', '')
        ]
        _call('write', SHEET_OUTBOUND, row=row, data=data)
        _update('last_push', datetime.now().isoformat())
        return {'success': True}
    except Exception as e:
        _err(True); _update('last_error', str(e))
        return {'success': False, 'message': str(e)}

def push_inbound_record(record):
    if not _sync_status['enabled']: return {'success': False}
    try:
        row = _get_next_row(SHEET_INBOUND)
        data = [
            str(row - 1), record.get('no', ''), record.get('date', ''),
            record.get('code', ''), record.get('name', ''),
            str(record.get('qty', 0)), str(record.get('price', 0)),
            str(record.get('amount', 0)), record.get('operator', ''),
            record.get('account', ''), record.get('warehouse', ''),
            record.get('supplier', ''), record.get('sn1', ''),
            record.get('sn2', ''), record.get('sn3', ''), record.get('remark', '')
        ]
        _call('write', SHEET_INBOUND, row=row, data=data)
        _update('last_push', datetime.now().isoformat())
        return {'success': True}
    except Exception as e:
        _err(True); _update('last_error', str(e))
        return {'success': False, 'message': str(e)}

def push_outbound_batch(records):
    if not records: return {'success': True, 'count': 0}
    ok, fail = 0, 0
    for rec in records:
        r = push_outbound_record(rec)
        if r.get('success'): ok += 1
        else: fail += 1
    _update('last_push', datetime.now().isoformat())
    return {'success': fail == 0, 'count': ok, 'failed': fail}

def push_inbound_batch(records):
    if not records: return {'success': True, 'count': 0}
    ok, fail = 0, 0
    for rec in records:
        r = push_inbound_record(rec)
        if r.get('success'): ok += 1
        else: fail += 1
    _update('last_push', datetime.now().isoformat())
    return {'success': fail == 0, 'count': ok, 'failed': fail}

def push_inventory(inventory_data):
    if not _sync_status['enabled']: return {'success': False}
    try:
        _call('clear', SHEET_INVENTORY)
        _call('writeHeader', SHEET_INVENTORY, headers=['物料编码','物料名称','入库数量','入库金额','出库数量','出库金额','当前库存','安全库存','状态','备注'])
        for i, item in enumerate(inventory_data):
            _call('write', SHEET_INVENTORY, row=i+2, data=[
                item.get('code',''), item.get('name',''),
                str(item.get('inQty',0)), str(item.get('inAmt',0)),
                str(item.get('outQty',0)), str(item.get('outAmt',0)),
                str(item.get('stock',0)), str(item.get('safety',1)),
                item.get('alert','正常'), ''
            ])
        _update('last_push', datetime.now().isoformat())
        return {'success': True, 'count': len(inventory_data)}
    except Exception as e:
        _err(True); _update('last_error', str(e))
        return {'success': False, 'message': str(e)}

# ============ 拉取 ============
def pull_sheet(sheet_name):
    try:
        r = _call('readRows', sheet_name, startRow=1, endRow=5000, cols=20)
        _update('last_pull', datetime.now().isoformat())
        if r and r.get('success'):
            return {'success': True, 'rows': r.get('data', []), 'count': len(r.get('data', []))}
        return {'success': True, 'rows': [], 'count': 0}
    except Exception as e:
        _err(False); _update('last_error', str(e))
        return {'success': False, 'message': str(e)}

def pull_all_and_replace():
    results = {'outbound': 0, 'inbound': 0, 'inventory': 0, 'success': False, 'errors': []}
    for name, sheet in [('outbound', SHEET_OUTBOUND), ('inbound', SHEET_INBOUND), ('inventory', SHEET_INVENTORY)]:
        r = pull_sheet(sheet)
        if r['success']: results[name] = r['count']
        else: results['errors'].append(f'{name}: {r.get("message")}')
    existing = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f: existing = json.load(f)
        except: pass
    new_data = {
        'inbound': [], 'outbound': [], 'inventory': [],
        'config': existing.get('config', {}),
        'payments': existing.get('payments', []),
        'receipts': existing.get('receipts', []),
        'transfers': existing.get('transfers', []),
    }
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    results['success'] = len(results['errors']) == 0
    return results

def get_status():
    with _status_lock: return dict(_sync_status)

def set_enabled(enabled):
    _update('enabled', bool(enabled))
    return {'success': True}

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
    return results

def init_wps_sheets():
    headers_out = ['序号','出库单号','日期','物料编码','物料名称','数量','售价','金额','操作员','收入账户','仓位','客户','SN序列号','退货单号','发票状态','进货单价','备注']
    headers_in = ['序号','入库单号','日期','物料编码','物料名称','数量','单价','金额','操作员','采购账户','仓位','供应商','SN1','SN2','SN3','备注']
    headers_inv = ['物料编码','物料名称','入库数量','入库金额','出库数量','出库金额','当前库存','安全库存','状态','备注']
    try:
        _call('writeHeader', SHEET_OUTBOUND, headers=headers_out)
        _call('writeHeader', SHEET_INBOUND, headers=headers_in)
        _call('writeHeader', SHEET_INVENTORY, headers=headers_inv)
        return {'success': True}
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_wps_status():
    result = {}
    for name, sheet in [('outbound', SHEET_OUTBOUND), ('inbound', SHEET_INBOUND), ('inventory', SHEET_INVENTORY)]:
        try:
            r = _call('readRows', sheet, startRow=1, endRow=5000, cols=1)
            result[name] = len(r.get('data', [])) if r and r.get('success') else -1
        except:
            result[name] = -1
    return {'success': True, 'result': result}
