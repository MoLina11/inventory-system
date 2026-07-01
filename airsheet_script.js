/**
 * 出入库管理系统 - WPS AirScript 1.0 脚本
 * 普通在线表格专用，已验证可用
 */
var globalResult = {};

var action = '';
var sheetName = '';
var rowsData = null;
var maxRowsVal = 500;

try {
  if (typeof Context !== 'undefined' && Context && Context.argv) {
    action = Context.argv.action || '';
    sheetName = Context.argv.sheet || '';
    rowsData = Context.argv.rows || null;
    maxRowsVal = Context.argv.maxRows || 500;
  }
} catch(e) {}

var SHEETS = {
  outbound: '销售出库明细表',
  inbound: '进货入库明细表',
  inventory: '库存统计表'
};

var HEADERS = {
  outbound: ['序号','出库单号','日期','物料编码','物料名称','数量','单价','金额','操作员','收入账户','仓位','客户','SN序列号','退货单号','发票状态','进货单价','备注'],
  inbound: ['序号','入库单号','日期','物料编码','物料名称','数量','单价','金额','操作员','采购账户','仓位','供应商','SN1','SN2','SN3','备注'],
  inventory: ['物料编码','物料名称','入库数量','入库金额','出库数量','出库金额','当前库存','安全库存','状态','备注']
};

try {
  if (action === 'headers') globalResult = doHeaders(sheetName);
  else if (action === 'append') globalResult = doAppend(sheetName, rowsData || []);
  else if (action === 'read') globalResult = doRead(sheetName, maxRowsVal);
  else if (action === 'clear') globalResult = doClear(sheetName);
  else if (action === 'write_all') globalResult = doWriteAll(sheetName, rowsData || []);
  else if (action === 'init') globalResult = doInit();
  else if (action === 'status') globalResult = doStatus();
  else globalResult = { error: '未知操作: ' + action };
} catch (e) {
  globalResult = { error: '执行错误: ' + (e.message || String(e)) };
}

function getSheet(name) {
  if (!name) return ActiveSheet;
  var sheets = Application.Sheets;
  for (var i = 1; i <= sheets.Count; i++) {
    if (sheets.Item(i).Name === name) { sheets.Item(i).Activate(); return ActiveSheet; }
  }
  sheets.Add(); ActiveSheet.Name = name; return ActiveSheet;
}

function getRowCount(sheet) {
  var m = 0;
  for (var r = 1; r <= 5000; r++) {
    var hasData = false;
    for (var c = 1; c <= 20; c++) {
      var v = sheet.Cells(r, c).Value2;
      if (v !== undefined && v !== null && v !== '') { hasData = true; break; }
    }
    if (hasData) m = r;
    else {
      var nextHas = false;
      for (var c = 1; c <= 20; c++) {
        var nv = sheet.Cells(r + 1, c).Value2;
        if (nv !== undefined && nv !== null && nv !== '') { nextHas = true; break; }
      }
      if (!nextHas) break;
    }
  }
  return m;
}

function setHeader(sheet, h) { for (var c = 0; c < h.length; c++) sheet.Cells(1, c + 1).Value2 = h[c]; }

function doHeaders(sn) {
  var s = getSheet(sn), rc = getRowCount(s), hd = [];
  if (rc > 0) {
    for (var c = 1; c <= 50; c++) {
      var v = s.Cells(1, c).Value2;
      if ((v === undefined || v === null || v === '') && c > 1) {
        var nv = s.Cells(1, c + 1).Value2;
        if (nv === undefined || nv === null || nv === '') break;
      }
      hd.push(v || '');
    }
  }
  return { headers: hd, rowCount: rc, sheetName: sn };
}

function doAppend(sn, rows) {
  if (!rows || !rows.length) return { error: 'rows参数为空' };
  var s = getSheet(sn), sr = getRowCount(s);
  if (sr === 0) {
    var keys = ['outbound', 'inbound', 'inventory'];
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      if (SHEETS[k] === sn && HEADERS[k]) { setHeader(s, HEADERS[k]); sr = 1; break; }
    }
  }
  for (var i = 0; i < rows.length; i++) {
    var tr = sr + 1 + i;
    for (var c = 0; c < rows[i].length; c++) s.Cells(tr, c + 1).Value2 = rows[i][c];
  }
  if (sr > 0) {
    for (var r = 2; r <= sr + rows.length; r++) {
      var ev = s.Cells(r, 1).Value2;
      if (ev === undefined || ev === null || ev === '' || !isNaN(Number(ev))) s.Cells(r, 1).Value2 = r - 1;
    }
  }
  return { success: true, appendedCount: rows.length, totalRows: sr + rows.length };
}

function doRead(sn, max) {
  var s = getSheet(sn), rc = getRowCount(s);
  if (rc === 0) return { headers: [], rows: [], rowCount: 0, sheetName: sn };
  var hd = [];
  for (var c = 1; c <= 50; c++) {
    var v = s.Cells(1, c).Value2;
    if ((v === undefined || v === null || v === '') && c > 1) {
      var nv = s.Cells(1, c + 1).Value2;
      if (nv === undefined || nv === null || nv === '') break;
    }
    hd.push(v !== undefined && v !== null ? String(v) : '');
  }
  var colCount = Math.max(hd.length, 20);
  var limit = Math.min(rc - 1, max || 500);
  var rows = [];
  for (var r = 2; r <= limit + 1; r++) {
    var row = [], hasData = false;
    for (var col = 1; col <= colCount; col++) {
      var cv = s.Cells(r, col).Value2;
      var sv = (cv !== undefined && cv !== null) ? String(cv) : '';
      row.push(sv);
      if (sv) hasData = true;
    }
    if (hasData) rows.push(row);
  }
  return { headers: hd, rows: rows, rowCount: rc, readCount: rows.length, sheetName: sn, truncated: (rc - 1) > limit };
}

function doClear(sn) {
  var s = getSheet(sn), rc = getRowCount(s);
  if (rc <= 1) return { success: true, clearedRows: 0 };
  for (var r = 2; r <= rc; r++) for (var c = 1; c <= 20; c++) s.Cells(r, c).Value2 = '';
  return { success: true, clearedRows: rc - 1 };
}

function doWriteAll(sn, rows) { doClear(sn); return doAppend(sn, rows); }

function doInit() {
  var res = {}, keys = ['outbound', 'inbound', 'inventory'];
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i];
    var s = getSheet(SHEETS[k]), rc = getRowCount(s);
    if (rc === 0 && HEADERS[k]) { setHeader(s, HEADERS[k]); res[k] = { success: true, msg: '已初始化表头' }; }
    else res[k] = { success: true, msg: '已有' + rc + '行' };
  }
  return res;
}

function doStatus() {
  var res = {}, keys = ['outbound', 'inbound', 'inventory'];
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i];
    try {
      var s = getSheet(SHEETS[k]), rc = getRowCount(s);
      res[k] = { sheetName: SHEETS[k], rowCount: rc, dataRows: Math.max(0, rc - 1) };
    } catch (e) { res[k] = { error: e.message || String(e) }; }
  }
  return res;
}

return globalResult;
