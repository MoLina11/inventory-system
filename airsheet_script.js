/**
 * 出入库管理系统 - WPS AirScript 2.0 脚本（智能表格专用）
 * 
 * 使用说明：
 * 1. 在 WPS 智能表格中创建 AirScript 2.0 脚本
 * 2. 粘贴此代码，Ctrl+S 保存
 * 3. 生成 Token + webhook
 * 
 * 2.0 特性：async/await、现代 JS、性能翻倍
 */
var globalResult = {};

// 入口：2.0 中 Context.argv 可正常获取
if (typeof Context !== 'undefined' && Context && Context.argv) {
  main();
}

async function main() {
  var argv = Context.argv;
  var action = argv.action || '';
  var sheetName = argv.sheet || '';

  try {
    if (action === 'headers') globalResult = await getHeaders(sheetName);
    else if (action === 'append') globalResult = await appendRows(sheetName, argv.rows || []);
    else if (action === 'read') globalResult = await readSheet(sheetName, argv.maxRows || 500);
    else if (action === 'clear') globalResult = await clearData(sheetName);
    else if (action === 'write_all') globalResult = await writeAll(sheetName, argv.rows || []);
    else if (action === 'init') globalResult = await initSheets();
    else if (action === 'status') globalResult = await getStatus();
    else globalResult = { error: '未知操作: ' + action };
  } catch (e) {
    globalResult = { error: e.message || String(e) };
  }
}

// ============ 配置 ============
const SHEETS = {
  outbound: '销售出库明细表',
  inbound: '进货入库明细表',
  inventory: '库存统计表'
};

const HEADERS = {
  outbound: ['序号','出库单号','日期','物料编码','物料名称','数量','单价','金额','操作员','收入账户','仓位','客户','SN序列号','退货单号','发票状态','进货单价','备注'],
  inbound: ['序号','入库单号','日期','物料编码','物料名称','数量','单价','金额','操作员','采购账户','仓位','供应商','SN1','SN2','SN3','备注'],
  inventory: ['物料编码','物料名称','入库数量','入库金额','出库数量','出库金额','当前库存','安全库存','状态','备注']
};

// ============ 工具函数 ============

function getSheet(name) {
  if (!name) return ActiveSheet;
  const sheets = Application.Sheets;
  for (let i = 1; i <= sheets.Count; i++) {
    if (sheets.Item(i).Name === name) {
      sheets.Item(i).Activate();
      return ActiveSheet;
    }
  }
  sheets.Add();
  ActiveSheet.Name = name;
  return ActiveSheet;
}

function getRowCount(sheet) {
  let m = 0;
  for (let r = 1; r <= 5000; r++) {
    let hasData = false;
    for (let c = 1; c <= 20; c++) {
      const v = sheet.Cells(r, c).Value2;
      if (v !== undefined && v !== null && v !== '') { hasData = true; break; }
    }
    if (hasData) m = r;
    else {
      let nextHas = false;
      for (let c = 1; c <= 20; c++) {
        const nv = sheet.Cells(r + 1, c).Value2;
        if (nv !== undefined && nv !== null && nv !== '') { nextHas = true; break; }
      }
      if (!nextHas) break;
    }
  }
  return m;
}

function setHeader(sheet, h) {
  for (let c = 0; c < h.length; c++) sheet.Cells(1, c + 1).Value2 = h[c];
}

// ============ 操作函数 ============

async function getHeaders(sheetName) {
  const sheet = getSheet(sheetName);
  const rc = getRowCount(sheet);
  const hd = [];
  if (rc > 0) {
    for (let c = 1; c <= 50; c++) {
      const v = sheet.Cells(1, c).Value2;
      if ((v === undefined || v === null || v === '') && c > 1) {
        const nv = sheet.Cells(1, c + 1).Value2;
        if (nv === undefined || nv === null || nv === '') break;
      }
      hd.push(v || '');
    }
  }
  return { headers: hd, rowCount: rc, sheetName: sheetName };
}

async function appendRows(sheetName, rows) {
  if (!rows || !rows.length) return { error: 'rows参数为空' };
  const sheet = getSheet(sheetName);
  let startRow = getRowCount(sheet);
  
  if (startRow === 0) {
    const keys = ['outbound', 'inbound', 'inventory'];
    for (const k of keys) {
      if (SHEETS[k] === sheetName && HEADERS[k]) { setHeader(sheet, HEADERS[k]); startRow = 1; break; }
    }
  }
  
  for (let i = 0; i < rows.length; i++) {
    const tr = startRow + 1 + i;
    for (let c = 0; c < rows[i].length; c++) sheet.Cells(tr, c + 1).Value2 = rows[i][c];
  }
  
  if (startRow > 0) {
    for (let r = 2; r <= startRow + rows.length; r++) {
      const ev = sheet.Cells(r, 1).Value2;
      if (ev === undefined || ev === null || ev === '' || !isNaN(Number(ev))) sheet.Cells(r, 1).Value2 = r - 1;
    }
  }
  
  return { success: true, appendedCount: rows.length, totalRows: startRow + rows.length };
}

async function readSheet(sheetName, maxRows) {
  const sheet = getSheet(sheetName);
  const rc = getRowCount(sheet);
  if (rc === 0) return { headers: [], rows: [], rowCount: 0, sheetName: sheetName };
  
  const hd = [];
  for (let c = 1; c <= 50; c++) {
    const v = sheet.Cells(1, c).Value2;
    if ((v === undefined || v === null || v === '') && c > 1) {
      const nv = sheet.Cells(1, c + 1).Value2;
      if (nv === undefined || nv === null || nv === '') break;
    }
    hd.push(v !== undefined && v !== null ? String(v) : '');
  }
  
  const colCount = Math.max(hd.length, 20);
  const limit = Math.min(rc - 1, maxRows || 500);
  const rows = [];
  
  for (let r = 2; r <= limit + 1; r++) {
    const row = [];
    let hasData = false;
    for (let col = 1; col <= colCount; col++) {
      const cv = sheet.Cells(r, col).Value2;
      const sv = (cv !== undefined && cv !== null) ? String(cv) : '';
      row.push(sv);
      if (sv) hasData = true;
    }
    if (hasData) rows.push(row);
  }
  
  return { headers: hd, rows: rows, rowCount: rc, readCount: rows.length, sheetName: sheetName, truncated: (rc - 1) > limit };
}

async function clearData(sheetName) {
  const sheet = getSheet(sheetName);
  const rc = getRowCount(sheet);
  if (rc <= 1) return { success: true, clearedRows: 0 };
  for (let r = 2; r <= rc; r++) for (let c = 1; c <= 20; c++) sheet.Cells(r, c).Value2 = '';
  return { success: true, clearedRows: rc - 1 };
}

async function writeAll(sheetName, rows) {
  await clearData(sheetName);
  return await appendRows(sheetName, rows);
}

async function initSheets() {
  const res = {};
  const keys = ['outbound', 'inbound', 'inventory'];
  for (const k of keys) {
    const sheet = getSheet(SHEETS[k]);
    const rc = getRowCount(sheet);
    if (rc === 0 && HEADERS[k]) { setHeader(sheet, HEADERS[k]); res[k] = { success: true, msg: '已初始化表头' }; }
    else res[k] = { success: true, msg: '已有' + rc + '行' };
  }
  return res;
}

async function getStatus() {
  const res = {};
  const keys = ['outbound', 'inbound', 'inventory'];
  for (const k of keys) {
    try {
      const sheet = getSheet(SHEETS[k]);
      const rc = getRowCount(sheet);
      res[k] = { sheetName: SHEETS[k], rowCount: rc, dataRows: Math.max(0, rc - 1) };
    } catch (e) { res[k] = { error: e.message || String(e) }; }
  }
  return res;
}

// 2.0 返回值：最后一个表达式
globalResult;
