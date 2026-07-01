/**
 * 出入库管理系统 — 出库自动化脚本
 * 当出库记录新增时，自动更新库存总览中对应 SN 的状态
 * 
 * 使用方式：在 AirScript 中新建脚本，粘贴此代码，
 * 在「触发器」中设置：出库记录 → 新增记录时 → 运行此脚本
 */

function onOutboundCreated() {
  var sheets = Application.Sheet.GetSheets();
  var outboundSheet, inventorySheet;
  
  for (var i = 0; i < sheets.length; i++) {
    if (sheets[i].name === '出库记录') outboundSheet = sheets[i];
    if (sheets[i].name === '库存总览') inventorySheet = sheets[i];
  }
  
  if (!outboundSheet || !inventorySheet) {
    console.log('❌ 未找到出库记录或库存总览表');
    return;
  }

  // 获取出库记录
  var outRecords = Application.Record.GetRecords({ SheetId: outboundSheet.id });
  if (!outRecords || !outRecords.records || outRecords.records.length === 0) {
    console.log('📭 出库记录为空');
    return;
  }

  // 获取库存记录
  var invRecords = Application.Record.GetRecords({ SheetId: inventorySheet.id });
  if (!invRecords || !invRecords.records) {
    console.log('📭 库存记录为空');
    return;
  }

  // 建立 SN → 库存记录ID 的映射
  var snMap = {};
  for (var j = 0; j < invRecords.records.length; j++) {
    var sn = invRecords.records[j].fields['SN'];
    if (sn) snMap[sn] = invRecords.records[j];
  }

  // 找出需要更新的库存记录
  var toUpdate = [];
  for (var k = 0; k < outRecords.records.length; k++) {
    var r = outRecords.records[k].fields;
    var sn = r['SN'];
    var invRec = snMap[sn];
    
    if (!sn || !invRec) continue;
    
    // 只更新状态为「在库」的
    if (invRec.fields['状态'] !== '在库') continue;
    
    toUpdate.push({
      id: invRec.id,
      fields: {
        '状态': '已出库',
        '出库日期': r['日期'] || '',
        '出库单号': r['单号'] || '',
        '客户': r['客户'] || '',
        '售价': r['售价'] || 0
      }
    });
  }

  if (toUpdate.length > 0) {
    Application.Record.UpdateRecords({
      SheetId: inventorySheet.id,
      Records: toUpdate
    });
    console.log('✅ 已更新', toUpdate.length, '条库存状态为「已出库」');
  } else {
    console.log('📭 没有需要更新的库存记录');
  }
}

onOutboundCreated();
