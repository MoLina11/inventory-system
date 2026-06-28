/**
 * 出入库管理系统 - WPS AirScript 2.0 脚本
 * 
 * 功能：通过 HTTP API 操作 WPS 电子表格
 * 使用方法：将此代码粘贴到 WPS 文档的 AirScript 脚本编辑器中（2.0 环境）
 * Webhook: https://www.kdocs.cn/api/v3/ide/file/ckY4M9Uert2l/script/V2-5IIsVnppcoztB1FmruFbUN/sync_task
 * Token: 4ixlDYFLLEks11xViYVoOf
 */

// ============ Sheet 名称配置 ============
const SHEETS = {
  outbound: '销售出库明细表',
  inbound: '进货入库明细表',
  inventory: '库存统计表'
};

// ============ 各 Sheet 表头定义 ============
const HEADERS = {
  outbound: [
    '序号', '出库单号', '日期', '物料编码', '物料名称',
    '数量', '单价', '金额', '操作员', '收入账户',
    '仓位', '客户', 'SN序列号', '退货单号', '发票状态',
    '进货单价', '备注'
  ],
  inbound: [
    '序号', '入库单号', '日期', '物料编码', '物料名称',
    '数量', '单价', '金额', '操作员', '采购账户',
    '仓位', '供应商', 'SN1', 'SN2', 'SN3', '备注'
  ],
  inventory: [
    '物料编码', '物料名称', '入库数量', '入库金额',
    '出库数量', '出库金额', '当前库存', '安全库存',
    '状态', '备注'
  ]
};

// ============ 主函数 ============
async function main() {
  // 注意：2.0 环境中 Context 是全局变量，不需要声明
  const argv = (typeof Context !== 'undefined' && Context.argv) ? Context.argv : {};
  const action = argv.action || '';
  const sheetName = argv.sheet || '';

  try {
    switch (action) {
      case 'headers':
        return getHeaders(sheetName);
      case 'append':
        return appendRows(sheetName, argv.rows || []);
      case 'read':
        return readSheet(sheetName, argv.maxRows || 500);
      case 'clear':
        return clearData(sheetName);
      case 'write_all':
        return writeAll(sheetName, argv.rows || []);
      case 'init':
        return initSheets();
      case 'status':
        return getStatus();
      default:
        return { error: `未知操作: "${action}"，支持: headers, append, read, clear, write_all, init, status` };
    }
  } catch (e) {
    return { error: e.message || String(e) };
  }
}

// ============ 工具函数 ============

/**
 * 获取或激活指定名称的 Sheet
 */
function getSheet(name) {
  if (!name) {
    return ActiveSheet;
  }
  const sheets = Application.Sheets;
  for (let i = 1; i <= sheets.Count; i++) {
    if (sheets.Item(i).Name === name) {
      sheets.Item(i).Activate();
      return ActiveSheet;
    }
  }
  // 不存在则创建
  sheets.Add();
  ActiveSheet.Name = name;
  return ActiveSheet;
}

/**
 * 获取 Sheet 的实际数据行数（从第1行开始找，直到遇到连续2个空行）
 */
function getDataRowCount(sheet) {
  let maxRow = 0;
  // 先快速检查 A 列
  for (let r = 1; r <= 5000; r++) {
    const val = sheet.Cells(r, 1).Value2;
    if (val !== undefined && val !== null && val !== '') {
      maxRow = r;
    } else {
      // 遇到空行，检查下一行是否也为空（防止中间有空行）
      const nextVal = sheet.Cells(r + 1, 1).Value2;
      if (nextVal === undefined || nextVal === null || nextVal === '') {
        break;
      }
    }
  }
  return maxRow;
}

/**
 * 设置表头
 */
function setHeader(sheet, headers) {
  for (let c = 0; c < headers.length; c++) {
    sheet.Cells(1, c + 1).Value2 = headers[c];
  }
  // 表头加粗
  const headerRange = sheet.Range(
    sheet.Cells(1, 1),
    sheet.Cells(1, headers.length)
  );
  try {
    headerRange.Font.Bold = true;
  } catch (e) {
    // 忽略格式设置失败
  }
}

// ============ 操作函数 ============

/**
 * 获取表头
 */
function getHeaders(sheetName) {
  const sheet = getSheet(sheetName);
  const rowCount = getDataRowCount(sheet);
  const headers = [];
  
  if (rowCount > 0) {
    // 读第一行作为表头
    let c = 1;
    while (true) {
      const val = sheet.Cells(1, c).Value2;
      if (val === undefined || val === null || val === '') {
        // 检查下一列
        const nextVal = sheet.Cells(1, c + 1).Value2;
        if (nextVal === undefined || nextVal === null || nextVal === '') {
          break;
        }
      }
      headers.push(val || '');
      c++;
      if (c > 50) break; // 安全限制
    }
  } else {
    // 新 Sheet，用默认表头
    const sheetType = Object.keys(SHEETS).find(k => SHEETS[k] === sheetName);
    return {
      headers: HEADERS[sheetType] || [],
      rowCount: 0,
      sheetName: sheetName,
      message: '新表格，已初始化表头'
    };
  }
  
  return {
    headers: headers,
    rowCount: rowCount,
    sheetName: sheetName
  };
}

/**
 * 追加数据行
 * rows: 二维数组，如 [['val1', 'val2'], ['val3', 'val4']]
 */
function appendRows(sheetName, rows) {
  if (!rows || rows.length === 0) {
    return { error: 'rows 参数为空' };
  }
  
  const sheet = getSheet(sheetName);
  let startRow = getDataRowCount(sheet);
  
  // 如果没有数据行，先写表头
  if (startRow === 0) {
    const sheetType = Object.keys(SHEETS).find(k => SHEETS[k] === sheetName);
    if (sheetType && HEADERS[sheetType]) {
      setHeader(sheet, HEADERS[sheetType]);
      startRow = 1;
    }
  }
  
  // 追加数据
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const targetRow = startRow + 1 + i;
    for (let c = 0; c < row.length; c++) {
      sheet.Cells(targetRow, c + 1).Value2 = row[c];
    }
  }
  
  // 更新序号列（A列）
  if (startRow > 0) {
    for (let r = 2; r <= startRow + rows.length; r++) {
      const existingVal = sheet.Cells(r, 1).Value2;
      if (existingVal === undefined || existingVal === null || existingVal === '' || !isNaN(Number(existingVal))) {
        sheet.Cells(r, 1).Value2 = r - 1;
      }
    }
  }
  
  return {
    success: true,
    appendedCount: rows.length,
    totalRows: startRow + rows.length
  };
}

/**
 * 读取 Sheet 数据
 * maxRows: 最大读取行数（避免超时），默认500
 */
function readSheet(sheetName, maxRows) {
  const sheet = getSheet(sheetName);
  const rowCount = getDataRowCount(sheet);
  
  if (rowCount === 0) {
    return {
      headers: [],
      rows: [],
      rowCount: 0,
      sheetName: sheetName
    };
  }
  
  // 读取表头
  const headers = [];
  let c = 1;
  while (true) {
    const val = sheet.Cells(1, c).Value2;
    if ((val === undefined || val === null || val === '') && c > 1) {
      const nextVal = sheet.Cells(1, c + 1).Value2;
      if (nextVal === undefined || nextVal === null || nextVal === '') {
        break;
      }
    }
    headers.push(val !== undefined && val !== null ? String(val) : '');
    c++;
    if (c > 50) break;
  }
  
  // 读取数据行（从第2行开始）
  const readLimit = Math.min(rowCount - 1, maxRows || 500);
  const rows = [];
  
  for (let r = 2; r <= readLimit + 1; r++) {
    const row = [];
    let hasData = false;
    for (let c = 1; c <= headers.length; c++) {
      const val = sheet.Cells(r, c).Value2;
      const strVal = (val !== undefined && val !== null) ? String(val) : '';
      row.push(strVal);
      if (strVal) hasData = true;
    }
    if (hasData) {
      rows.push(row);
    }
  }
  
  return {
    headers: headers,
    rows: rows,
    rowCount: rowCount,
    readCount: rows.length,
    sheetName: sheetName,
    truncated: (rowCount - 1) > readLimit
  };
}

/**
 * 清空数据区（保留表头）
 */
function clearData(sheetName) {
  const sheet = getSheet(sheetName);
  const rowCount = getDataRowCount(sheet);
  
  if (rowCount <= 1) {
    return { success: true, clearedRows: 0, message: '没有数据需要清除' };
  }
  
  const colCount = 20; // 预设列数
  
  // 清空第2行开始的所有数据
  for (let r = 2; r <= rowCount; r++) {
    for (let c = 1; c <= colCount; c++) {
      sheet.Cells(r, c).Value2 = '';
    }
  }
  
  return {
    success: true,
    clearedRows: rowCount - 1
  };
}

/**
 * 全量写入（先清空再写入）
 */
function writeAll(sheetName, rows) {
  // 先清空
  clearData(sheetName);
  
  // 再追加
  return appendRows(sheetName, rows);
}

/**
 * 初始化所有 Sheet（设置表头）
 */
function initSheets() {
  const results = {};
  
  for (const [key, name] of Object.entries(SHEETS)) {
    const sheet = getSheet(name);
    const rowCount = getDataRowCount(sheet);
    
    if (rowCount === 0 && HEADERS[key]) {
      setHeader(sheet, HEADERS[key]);
      results[key] = { success: true, message: '已初始化表头' };
    } else {
      results[key] = { success: true, message: `已有 ${rowCount} 行数据` };
    }
  }
  
  return results;
}

/**
 * 获取所有 Sheet 的状态
 */
function getStatus() {
  const result = {};
  
  for (const [key, name] of Object.entries(SHEETS)) {
    try {
      const sheet = getSheet(name);
      const rowCount = getDataRowCount(sheet);
      result[key] = {
        sheetName: name,
        rowCount: rowCount,
        dataRows: Math.max(0, rowCount - 1)
      };
    } catch (e) {
      result[key] = { sheetName: name, error: e.message || String(e) };
    }
  }
  
  return result;
}

// ============ 执行入口 ============
// 2.0 环境：main() 的返回值自动作为脚本执行结果返回
return main();
