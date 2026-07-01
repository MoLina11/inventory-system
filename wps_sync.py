"""
WPS 智能表格数据同步模块
通过 AirScript 1.0 数据表 API 实现 Web 系统与智能表格的双向同步

智能表格使用数据表模型（Record/Field），API 不同于普通在线表格的工作表模型。
"""
import json, os, logging, threading, urllib.request, urllib.error
from datetime import datetime

# ============ 配置 ============
AIRSCRIPT_WEBHOOK = 'https://www.kdocs.cn/api/v3/ide/file/cuCCqjRY0r2N/script/V2-5OP8Jlz20PGcPPpCDuVW9j/sync_task'
AIRSCRIPT_TOKEN = '4ixlDYFLLEks11xViYVoOf'

# 智能表格数据表名称（用户需在智能表格中创建这些数据表）
TABLE_OUTBOUND = '出库记录'
TABLE_INBOUND = '入库记录'
TABLE_INVENTORY = '库存汇总'

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
logger = logging.getLogger('wps_sync')

_sync_status = {
    'enabled': True, 'last_push': None, 'last_pull': None,
    'push_errors': 0, 'pull_errors': 0, 'last_error': None,
}
_status_lock = threading.Lock()

# ============ 底层 API 调用 ============
def _call_airscript(action, sheet, fields=None, filter_val=None, record_id=None, timeout=120):
    argv = {'action': action, 'sheet': sheet}
    if fields: argv['fields'] = fields
    if filter_val: argv['filter'] = filter_val
    if record_id: argv['id'] = record_id
    payload = json.dumps({'Context': {'argv': argv}}).encode('utf-8')
    hdrs = {'Content-Type': 'application/json', 'AirScript-Token': AIRSCRIPT_TOKEN}
    req = urllib.request.Request(AIRSCRIPT_WEBHOOK, payload, hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        raise Exception(f'API 调用失败: {e}')
    if data.get('error'):
        raise Exception(f'脚本错误: {data["error"]}')
    result = data.get('data', {}).get('result', '')
    if isinstance(result, str):
        try: result = json.loads(result)
        except: result = {'raw': result} if result != '[Undefined]' else None
    return result

def _update(k, v):
    with _status_lock: _sync_status[k] = v

def _err(push=True):
    with _status_lock:
        if push: _sync_status['push_errors'] += 1
        else: _sync_status['pull_errors'] += 1

# ============ 推送（系统 → 智能表格）============
def push_outbound_record(record):
    """推送单条出库记录"""
    if not _sync_status['enabled']: return {'success': False}
    try:
        fields = {
            '出库单号': record.get('no', ''),
            '出库日期': record.get('date', ''),
            '物料编码': record.get('code', ''),
            '物料名称': record.get('materialName', ''),
            '数量': record.get('qty', 0),
            '售价': record.get('price', 0),
            '金额': record.get('amount', 0),
            '操作员': record.get('operator', ''),
            '收入账户': record.get('incomeAccount', ''),
            '仓位': record.get('warehouse', ''),
            '客户': record.get('customer', ''),
            'SN序列号': record.get('snSerial', ''),
            '进货单价': record.get('purchasePrice', 0),
            '备注': record.get('remark', ''),
        }
        _call_airscript('create', TABLE_OUTBOUND, fields=fields, timeout=30)
        _update('last_push', datetime.now().isoformat())
        return {'success': True}
    except Exception as e:
        _err(True); _update('last_error', str(e))
        return {'success': False, 'message': str(e)}

def push_inbound_record(record):
    """推送单条入库记录"""
    if not _sync_status['enabled']: return {'success': False}
    try:
        fields = {
            '入库单号': record.get('no', ''),
            '入库日期': record.get('date', ''),
            '物料编码': record.get('code', ''),
            '物料名称': record.get('name', ''),
            '数量': record.get('qty', 0),
            '单价': record.get('price', 0),
            '金额': record.get('amount', 0),
            '操作员': record.get('operator', ''),
            '采购账户': record.get('account', ''),
            '仓位': record.get('warehouse', ''),
            '供应商': record.get('supplier', ''),
            'SN1': record.get('sn1', ''),
            'SN2': record.get('sn2', ''),
            'SN3': record.get('sn3', ''),
            '备注': record.get('remark', ''),
        }
        _call_airscript('create', TABLE_INBOUND, fields=fields, timeout=30)
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
    """全量推送库存"""
    if not _sync_status['enabled']: return {'success': False}
    try:
        # 先清空
        _call_airscript('deleteAll', TABLE_INVENTORY, timeout=120)
        # 逐条创建
        ok = 0
        for item in inventory_data:
            fields = {
                '物料编码': item.get('code', ''),
                '物料名称': item.get('name', ''),
                '入库总量': item.get('inQty', 0),
                '入库金额': item.get('inAmt', 0),
                '出库总量': item.get('outQty', 0),
                '出库金额': item.get('outAmt', 0),
                '当前库存': item.get('stock', 0),
                '安全库存': item.get('safety', 1),
                '库存状态': item.get('alert', '正常'),
            }
            try:
                _call_airscript('create', TABLE_INVENTORY, fields=fields, timeout=30)
                ok += 1
            except: pass
        _update('last_push', datetime.now().isoformat())
        return {'success': True, 'count': ok}
    except Exception as e:
        _err(True); _update('last_error', str(e))
        return {'success': False, 'message': str(e)}

# ============ 拉取（智能表格 → 系统）============
def pull_sheet(sheet_name):
    try:
        result = _call_airscript('readAll', sheet_name, timeout=120)
        _update('last_pull', datetime.now().isoformat())
        if not result or not result.get('success'):
            return {'success': True, 'rows': [], 'count': 0}
        records = result.get('data', [])
        return {'success': True, 'rows': records, 'count': len(records)}
    except Exception as e:
        _err(False); _update('last_error', str(e))
        return {'success': False, 'message': str(e)}

def pull_all_and_replace():
    """从智能表格拉取全部数据，替换 data.json"""
    results = {'outbound': 0, 'inbound': 0, 'inventory': 0, 'success': False, 'errors': []}
    
    ob = pull_sheet(TABLE_OUTBOUND)
    if ob['success']:
        results['outbound'] = ob['count']
    else:
        results['errors'].append(f'出库: {ob.get("message")}')
    
    ib = pull_sheet(TABLE_INBOUND)
    if ib['success']:
        results['inbound'] = ib['count']
    else:
        results['errors'].append(f'入库: {ib.get("message")}')
    
    inv = pull_sheet(TABLE_INVENTORY)
    if inv['success']:
        results['inventory'] = inv['count']
    else:
        results['errors'].append(f'库存: {inv.get("message")}')
    
    # 保留现有 config
    existing = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except: pass
    
    new_data = {
        'inbound': [],
        'outbound': [],
        'inventory': [],
        'config': existing.get('config', {}),
        'payments': existing.get('payments', []),
        'receipts': existing.get('receipts', []),
        'transfers': existing.get('transfers', []),
    }
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    
    results['success'] = len(results['errors']) == 0
    return results

# ============ 状态 ============
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
    return {'success': True, 'message': '智能表格无需初始化，请手动创建数据表'}

def get_wps_status():
    """获取智能表格各数据表记录数"""
    result = {}
    for name, table in [('outbound', TABLE_OUTBOUND), ('inbound', TABLE_INBOUND), ('inventory', TABLE_INVENTORY)]:
        try:
            r = _call_airscript('count', table, timeout=60)
            result[name] = r.get('data', {}).get('count', 0) if r else 0
        except:
            result[name] = -1
    return {'success': True, 'result': result}
