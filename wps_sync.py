"""
WPS 金山文档数据同步模块
通过 AirScript API 实现 PythonAnywhere 后端与 WPS 共享文档的双向同步
"""

import json
import time
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime

# ============ 配置 ============
AIRSCRIPT_WEBHOOK = 'https://www.kdocs.cn/api/v3/ide/file/ckY4M9Uert2l/script/V2-5IIsVnppcoztB1FmruFbUN/sync_task'
AIRSCRIPT_TOKEN = '4ixlDYFLLEks11xViYVoOf'

# Sheet 名称
SHEET_OUTBOUND = '销售出库明细表'
SHEET_INBOUND = '进货入库明细表'
SHEET_INVENTORY = '库存统计表'

# 同步日志
logger = logging.getLogger('wps_sync')

# 同步状态（线程安全）
_sync_status = {
    'enabled': True,
    'last_push': None,
    'last_pull': None,
    'push_errors': 0,
    'pull_errors': 0,
    'last_error': None,
    'pending_count': 0,
}
_status_lock = threading.Lock()


# ============ 底层 API 调用 ============

def _call_airscript(action, sheet=None, rows=None, max_rows=None, timeout=60):
    """
    调用 AirScript API
    
    Args:
        action: 操作名称 (headers/append/read/clear/write_all/init/status)
        sheet: Sheet 名称
        rows: 数据行（二维数组）
        max_rows: 最大读取行数
        timeout: 超时时间（秒）
    
    Returns:
        dict: API 返回的 result 对象
    """
    argv = {'action': action}
    if sheet:
        argv['sheet'] = sheet
    if rows is not None:
        argv['rows'] = rows
    if max_rows is not None:
        argv['maxRows'] = max_rows
    
    payload = json.dumps({
        'Context': {
            'argv': argv
        }
    }).encode('utf-8')
    
    headers = {
        'Content-Type': 'application/json',
        'AirScript-Token': AIRSCRIPT_TOKEN,
    }
    
    req = urllib.request.Request(AIRSCRIPT_WEBHOOK, payload, headers)
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        raise Exception(f'AirScript API HTTP {e.code}: {err_body[:500]}')
    except urllib.error.URLError as e:
        raise Exception(f'AirScript API 网络错误: {str(e.reason)}')
    except json.JSONDecodeError as e:
        raise Exception(f'AirScript API 返回格式错误: {str(e)}')
    except Exception as e:
        raise Exception(f'AirScript API 调用失败: {str(e)}')
    
    # 检查 API 错误
    if data.get('error'):
        error_details = data.get('error_details', {})
        detail_msg = error_details.get('msg', '') or error_details.get('name', '')
        raise Exception(f'AirScript 执行错误: {data["error"]} {detail_msg}')
    
    # 解析 result
    result = data.get('data', {}).get('result', '')
    
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            if result == '[Undefined]':
                result = None
            else:
                result = {'raw': result}
    
    return result


def _update_status(key, value):
    """线程安全地更新同步状态"""
    with _status_lock:
        _sync_status[key] = value


def _increment_error(push=True):
    """增加错误计数"""
    with _status_lock:
        if push:
            _sync_status['push_errors'] += 1
        else:
            _sync_status['pull_errors'] += 1


# ============ 推送操作（Python → WPS）============

def push_inbound_record(record):
    """
    推送单条入库记录到 WPS「进货入库明细表」
    
    Args:
        record: 入库记录字典
    Returns:
        dict: {'success': bool, 'message': str}
    """
    if not _sync_status['enabled']:
        return {'success': False, 'message': '同步已禁用'}
    
    try:
        row = [
            '',  # 序号（脚本自动填充）
            record.get('no', ''),
            record.get('date', ''),
            record.get('code', ''),
            record.get('name', ''),
            str(record.get('qty', 0)),
            str(record.get('price', 0)),
            str(record.get('amount', 0)),
            record.get('operator', ''),
            record.get('account', ''),
            record.get('warehouse', ''),
            record.get('supplier', ''),
            record.get('sn1', ''),
            record.get('sn2', ''),
            record.get('sn3', ''),
            record.get('remark', ''),
        ]
        
        result = _call_airscript('append', sheet=SHEET_INBOUND, rows=[row])
        
        _update_status('last_push', datetime.now().isoformat())
        logger.info(f'WPS 同步: 入库 {record.get("no")} 推送成功')
        
        return {'success': True, 'message': '推送成功'}
        
    except Exception as e:
        _increment_error(push=True)
        _update_status('last_error', str(e))
        logger.error(f'WPS 同步: 入库 {record.get("no")} 推送失败: {e}')
        return {'success': False, 'message': str(e)}


def push_outbound_record(record):
    """
    推送单条出库记录到 WPS「销售出库明细表」
    
    Args:
        record: 出库记录字典
    Returns:
        dict: {'success': bool, 'message': str}
    """
    if not _sync_status['enabled']:
        return {'success': False, 'message': '同步已禁用'}
    
    try:
        row = [
            '',  # 序号（脚本自动填充）
            record.get('no', ''),
            record.get('date', ''),
            record.get('code', ''),
            record.get('materialName', ''),
            str(record.get('qty', 0)),
            str(record.get('price', 0)),
            str(record.get('amount', 0)),
            record.get('operator', ''),
            record.get('incomeAccount', ''),
            record.get('warehouse', ''),
            record.get('customer', ''),
            record.get('snSerial', ''),
            record.get('returnNo', ''),
            record.get('invoiceStatus', ''),
            str(record.get('purchasePrice', 0)),
            record.get('remark', ''),
        ]
        
        result = _call_airscript('append', sheet=SHEET_OUTBOUND, rows=[row])
        
        _update_status('last_push', datetime.now().isoformat())
        logger.info(f'WPS 同步: 出库 {record.get("no")} 推送成功')
        
        return {'success': True, 'message': '推送成功'}
        
    except Exception as e:
        _increment_error(push=True)
        _update_status('last_error', str(e))
        logger.error(f'WPS 同步: 出库 {record.get("no")} 推送失败: {e}')
        return {'success': False, 'message': str(e)}


def push_inbound_batch(records):
    """批量推送入库记录"""
    if not _sync_status['enabled']:
        return {'success': False, 'message': '同步已禁用'}
    
    if not records:
        return {'success': True, 'message': '无数据', 'count': 0}
    
    try:
        rows = []
        for record in records:
            rows.append([
                '',
                record.get('no', ''),
                record.get('date', ''),
                record.get('code', ''),
                record.get('name', ''),
                str(record.get('qty', 0)),
                str(record.get('price', 0)),
                str(record.get('amount', 0)),
                record.get('operator', ''),
                record.get('account', ''),
                record.get('warehouse', ''),
                record.get('supplier', ''),
                record.get('sn1', ''),
                record.get('sn2', ''),
                record.get('sn3', ''),
                record.get('remark', ''),
            ])
        
        result = _call_airscript('append', sheet=SHEET_INBOUND, rows=rows)
        
        _update_status('last_push', datetime.now().isoformat())
        logger.info(f'WPS 同步: 批量入库 {len(rows)} 条推送成功')
        
        return {'success': True, 'message': f'推送成功', 'count': len(rows)}
        
    except Exception as e:
        _increment_error(push=True)
        _update_status('last_error', str(e))
        logger.error(f'WPS 同步: 批量入库推送失败: {e}')
        return {'success': False, 'message': str(e)}


def push_outbound_batch(records):
    """批量推送出库记录"""
    if not _sync_status['enabled']:
        return {'success': False, 'message': '同步已禁用'}
    
    if not records:
        return {'success': True, 'message': '无数据', 'count': 0}
    
    try:
        rows = []
        for record in records:
            rows.append([
                '',
                record.get('no', ''),
                record.get('date', ''),
                record.get('code', ''),
                record.get('materialName', ''),
                str(record.get('qty', 0)),
                str(record.get('price', 0)),
                str(record.get('amount', 0)),
                record.get('operator', ''),
                record.get('incomeAccount', ''),
                record.get('warehouse', ''),
                record.get('customer', ''),
                record.get('snSerial', ''),
                record.get('returnNo', ''),
                record.get('invoiceStatus', ''),
                str(record.get('purchasePrice', 0)),
                record.get('remark', ''),
            ])
        
        result = _call_airscript('append', sheet=SHEET_OUTBOUND, rows=rows)
        
        _update_status('last_push', datetime.now().isoformat())
        logger.info(f'WPS 同步: 批量出库 {len(rows)} 条推送成功')
        
        return {'success': True, 'message': f'推送成功', 'count': len(rows)}
        
    except Exception as e:
        _increment_error(push=True)
        _update_status('last_error', str(e))
        logger.error(f'WPS 同步: 批量出库推送失败: {e}')
        return {'success': False, 'message': str(e)}


def push_inventory(inventory_data):
    """
    全量推送库存数据到 WPS「库存统计表」
    
    Args:
        inventory_data: 库存列表
    """
    if not _sync_status['enabled']:
        return {'success': False, 'message': '同步已禁用'}
    
    try:
        rows = []
        for item in inventory_data:
            stock_qty = item.get('stock', 0)
            safety = item.get('safety', 1)
            alert = item.get('alert', '正常')
            
            rows.append([
                item.get('code', ''),
                item.get('name', ''),
                str(item.get('inQty', 0)),
                str(item.get('inAmt', 0)),
                str(item.get('outQty', 0)),
                str(item.get('outAmt', 0)),
                str(stock_qty),
                str(safety),
                alert,
                '',  # 备注
            ])
        
        result = _call_airscript('write_all', sheet=SHEET_INVENTORY, rows=rows)
        
        _update_status('last_push', datetime.now().isoformat())
        logger.info(f'WPS 同步: 库存 {len(rows)} 条全量推送成功')
        
        return {'success': True, 'message': f'推送成功', 'count': len(rows)}
        
    except Exception as e:
        _increment_error(push=True)
        _update_status('last_error', str(e))
        logger.error(f'WPS 同步: 库存推送失败: {e}')
        return {'success': False, 'message': str(e)}


# ============ 拉取操作（WPS → Python）============

def pull_sheet(sheet_name):
    """
    从 WPS 拉取指定 Sheet 的数据
    
    Args:
        sheet_name: Sheet 名称
    Returns:
        dict: {'success': bool, 'headers': [], 'rows': [[]], 'rowCount': int}
    """
    try:
        result = _call_airscript('read', sheet=sheet_name, max_rows=500)
        
        _update_status('last_pull', datetime.now().isoformat())
        
        if result is None:
            return {'success': True, 'headers': [], 'rows': [], 'rowCount': 0}
        
        return {
            'success': True,
            'headers': result.get('headers', []),
            'rows': result.get('rows', []),
            'rowCount': result.get('rowCount', 0),
            'readCount': result.get('readCount', 0),
            'truncated': result.get('truncated', False),
        }
        
    except Exception as e:
        _increment_error(push=False)
        _update_status('last_error', str(e))
        logger.error(f'WPS 同步: 拉取 {sheet_name} 失败: {e}')
        return {'success': False, 'message': str(e)}


def pull_all_sheets():
    """拉取所有 Sheet 数据"""
    results = {}
    for name, label in [('outbound', SHEET_OUTBOUND), ('inbound', SHEET_INBOUND), ('inventory', SHEET_INVENTORY)]:
        results[name] = pull_sheet(label)
    return results


# ============ 状态查询 ============

def get_status():
    """获取同步状态"""
    with _status_lock:
        return dict(_sync_status)


def set_enabled(enabled):
    """设置同步开关"""
    _update_status('enabled', bool(enabled))
    return {'success': True, 'enabled': bool(enabled)}


def reset_errors():
    """重置错误计数"""
    with _status_lock:
        _sync_status['push_errors'] = 0
        _sync_status['pull_errors'] = 0
        _sync_status['last_error'] = None
    return {'success': True}


# ============ 全量同步 ============

def full_push(data):
    """
    全量推送：将所有数据推送到 WPS
    
    Args:
        data: 包含 inbound/outbound/inventory 的数据字典
    """
    results = {}
    
    # 推送入库
    inbound = data.get('inbound', [])
    if inbound:
        results['inbound'] = push_inbound_batch(inbound)
    else:
        results['inbound'] = {'success': True, 'message': '无入库数据', 'count': 0}
    
    # 推送出库
    outbound = data.get('outbound', [])
    if outbound:
        results['outbound'] = push_outbound_batch(outbound)
    else:
        results['outbound'] = {'success': True, 'message': '无出库数据', 'count': 0}
    
    # 推送库存
    inventory = data.get('inventory', [])
    if inventory:
        results['inventory'] = push_inventory(inventory)
    else:
        results['inventory'] = {'success': True, 'message': '无库存数据', 'count': 0}
    
    _update_status('last_push', datetime.now().isoformat())
    
    return results


def init_wps_sheets():
    """初始化 WPS 中的 Sheet（设置表头）"""
    try:
        result = _call_airscript('init')
        return {'success': True, 'result': result}
    except Exception as e:
        return {'success': False, 'message': str(e)}


def get_wps_status():
    """获取 WPS 中各 Sheet 的状态"""
    try:
        result = _call_airscript('status')
        return {'success': True, 'result': result}
    except Exception as e:
        return {'success': False, 'message': str(e)}
