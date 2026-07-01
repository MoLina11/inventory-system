/**
 * 出入库管理系统 — 入库自动化脚本
 * 当入库记录新增时，自动在库存总览中创建对应 SN 记录
 * 
 * 使用方式：在 AirScript 中新建脚本，粘贴此代码，
 * 在「触发器」中设置：入库记录 → 新增记录时 → 运行此脚本
 */

function onInboundCreated() {
  // 获取所有工作表
  var sheets = Application.Sheet.GetSheets();
  var inboundSheet, inventorySheet;
  
  for (var i = 0; i < sheets.length; i++) {
    if (sheets[i].name === '入库记录') inboundSheet = sheets[i];
    if (sheets[i].name === '库存总览') inventorySheet = sheets[i];
  }
  
  if (!inboundSheet || !inventorySheet) {
    console.log('❌ 未找到入库记录或库存总览表');
    return;
  }

  // 获取入库记录中所有数据
  var records = Application.Record.GetRecords({ SheetId: inboundSheet.id });
  if (!records || !records.records || records.records.length === 0) {
    console.log('📭 入库记录为空');
    return;
  }

  // 获取库存中已有的 SN 列表
  var invRecords = Application.Record.GetRecords({ SheetId: inventorySheet.id });
  var existingSNs = {};
  if (invRecords && invRecords.records) {
    for (var j = 0; j < invRecords.records.length; j++) {
      var sn = invRecords.records[j].fields['SN'];
      if (sn) existingSNs[sn] = true;
    }
  }

  // 遍历入库记录，找出需要新增到库存的
  var toCreate = [];
  for (var k = 0; k < records.records.length; k++) {
    var r = records.records[k].fields;
    var sn = r['SN'];
    var status = r['状态'];
    
    // 跳过没有 SN 或已经在库存中的记录
    if (!sn || existingSNs[sn]) continue;
    
    toCreate.push({
      fields: {
        'SN': sn,
        '编码': r['编码'] || '',
        '名称': r['名称'] || '',
        '仓位': r['仓位'] || '',
        '进价': r['进价'] || 0,
        '状态': '在库',
        '入库日期': r['日期'] || '',
        '入库单号': r['单号'] || '',
        '操作人': r['操作人'] || ''
      }
    });
    existingSNs[sn] = true;
  }

  if (toCreate.length > 0) {
    Application.Record.CreateRecords({
      SheetId: inventorySheet.id,
      Records: toCreate
    });
    console.log('✅ 库存总览新增', toCreate.length, '条 SN 记录');
  } else {
    console.log('📭 没有需要新增的库存记录');
  }
}

onInboundCreated();
