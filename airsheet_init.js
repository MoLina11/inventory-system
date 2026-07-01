/**
 * 出入库管理系统 — 智能表格初始化脚本
 * 运行此脚本一键创建所有数据表、字段、视图
 * 
 * 使用方式：
 * 1. 打开智能表格 https://www.kdocs.cn/l/cuCCqjRY0r2N
 * 2. 点击「效率工具」→「AirScript」→「新建脚本」
 * 3. 粘贴此代码 → 点击运行
 */

function main() {
  // ========== 先删除已有的工作表（从头开始） ==========
  var sheets = Application.Sheet.GetSheets();
  console.log('当前工作表数量:', sheets.length);
  
  // 删除所有现有工作表
  for (var i = sheets.length - 1; i >= 0; i--) {
    try {
      Application.Sheet.DeleteSheet({ SheetId: sheets[i].id });
      console.log('已删除:', sheets[i].name);
    } catch(e) {
      console.log('删除失败:', sheets[i].name, e.message);
    }
  }

  // ========== 1. 创建「物料表」 ==========
  var materialSheet = Application.Sheet.CreateSheet({
    Name: '物料表',
    Fields: [
      { name: '编码', type: 'MultiLineText' },
      { name: '名称', type: 'MultiLineText' },
      { name: '规格', type: 'MultiLineText' },
      { name: '默认进价', type: 'Currency' },
      { name: '默认售价', type: 'Currency' },
      { name: '默认供应商', type: 'MultiLineText' },
      { name: '备注', type: 'MultiLineText' }
    ],
    Views: [
      { name: '物料列表', type: 'Grid' }
    ]
  });
  console.log('✅ 物料表已创建:', materialSheet.id);

  // 插入物料基础数据
  var materials = [
    { 编码: '6973555480693', 名称: '大我B13', 默认进价: 3500, 默认售价: 3899, 默认供应商: '深圳大我' },
    { 编码: '6973555480891', 名称: '大我B7pro-C绿色', 默认进价: 1960, 默认售价: 2199, 默认供应商: '深圳大我' },
    { 编码: '6973555480907', 名称: '大我B7pro-C白色', 默认进价: 1960, 默认售价: 2199, 默认供应商: '深圳大我' },
    { 编码: '6973555480884', 名称: '大我B7pro-C蓝色', 默认进价: 1960, 默认售价: 2199, 默认供应商: '深圳大我' },
    { 编码: '6973555480730', 名称: '大我B6C黑色', 默认进价: 950, 默认售价: 1017, 默认供应商: '深圳大我' },
    { 编码: '6973555480761', 名称: '大我B6C绿色', 默认进价: 950, 默认售价: 1017, 默认供应商: '深圳大我' },
    { 编码: '6973555480754', 名称: '大我B6C白色', 默认进价: 950, 默认售价: 1017, 默认供应商: '深圳大我' },
    { 编码: '6973555480709', 名称: 'B531CS大我HiBreak-S-C白色', 默认进价: 1200, 默认售价: 1399, 默认供应商: '深圳大我' },
    { 编码: '6973555480792', 名称: 'B651C大我HiBreak pro-C白色', 默认进价: 2400, 默认售价: 2829, 默认供应商: '深圳大我' },
    { 编码: '6973555480808', 名称: 'B651C大我HiBreak pro-C黑色', 默认进价: 2400, 默认售价: 2829, 默认供应商: '深圳大我' },
    { 编码: '6973555480938', 名称: '大我B10-C白色', 默认进价: 1800, 默认售价: 2099, 默认供应商: '深圳大我' },
    { 编码: '6973555480600', 名称: '大我B1051c pro', 默认进价: 1500, 默认售价: 1799, 默认供应商: '深圳大我' },
    { 编码: '6973555480815', 名称: '大我B751电容笔（C1）', 默认进价: 200, 默认售价: 299, 默认供应商: '深圳大我' },
    { 编码: '6974417015558', 名称: '国悦K3Color', 默认进价: 2800, 默认售价: 3299, 默认供应商: '深圳国阅' },
    { 编码: 'BMA5B', 名称: '大我A5电磁笔', 默认进价: 150, 默认售价: 199, 默认供应商: '深圳大我' },
    { 编码: 'BMC7B', 名称: '大我C7电容笔', 默认进价: 180, 默认售价: 239, 默认供应商: '深圳大我' },
  ];

  if (materials.length > 0) {
    Application.Record.CreateRecords({
      SheetId: materialSheet.id,
      Records: materials.map(function(m) {
        return { fields: { 编码: m.编码, 名称: m.名称, 默认进价: m.默认进价, 默认售价: m.默认售价, 默认供应商: m.默认供应商 } };
      })
    });
    console.log('📦 已插入', materials.length, '条物料数据');
  }

  // ========== 2. 创建「入库记录」 ==========
  var inboundSheet = Application.Sheet.CreateSheet({
    Name: '入库记录',
    Fields: [
      { name: '单号', type: 'MultiLineText' },
      { name: '日期', type: 'Date' },
      { name: '编码', type: 'MultiLineText' },
      { name: '名称', type: 'MultiLineText' },
      { name: 'SN', type: 'MultiLineText' },
      { name: '数量', type: 'Number' },
      { name: '进价', type: 'Currency' },
      { name: '金额', type: 'Currency' },
      { name: '仓位', type: 'SingleSelect', items: [{ value: '广州百脑汇仓' }, { value: '深圳大我仓' }] },
      { name: '采购账户', type: 'SingleSelect', items: [{ value: '广州彩次元' }, { value: '广东北斗' }, { value: '华个人帐' }, { value: '售后换新' }, { value: '门店销售' }] },
      { name: '供应商', type: 'SingleSelect', items: [{ value: '深圳大我' }, { value: '深圳国阅' }, { value: '深圳掌阅' }, { value: '广州格凡' }] },
      { name: '操作人', type: 'MultiLineText' },
      { name: '备注', type: 'MultiLineText' },
      { name: '创建时间', type: 'CreatedTime' }
    ],
    Views: [
      { name: '入库列表', type: 'Grid' },
      { name: '按仓位', type: 'Kanban' }
    ]
  });
  console.log('✅ 入库记录已创建:', inboundSheet.id);

  // ========== 3. 创建「出库记录」 ==========
  var outboundSheet = Application.Sheet.CreateSheet({
    Name: '出库记录',
    Fields: [
      { name: '单号', type: 'MultiLineText' },
      { name: '日期', type: 'Date' },
      { name: 'SN', type: 'MultiLineText' },
      { name: '编码', type: 'MultiLineText' },
      { name: '名称', type: 'MultiLineText' },
      { name: '数量', type: 'Number' },
      { name: '售价', type: 'Currency' },
      { name: '金额', type: 'Currency' },
      { name: '进价', type: 'Currency' },
      { name: '利润', type: 'Currency' },
      { name: '仓位', type: 'SingleSelect', items: [{ value: '广州百脑汇仓' }, { value: '深圳大我仓' }] },
      { name: '客户', type: 'SingleSelect', items: [{ value: 'PDD彩次元' }, { value: 'JD个人' }, { value: 'TB个人' }, { value: 'XY个人' }, { value: 'DY个人' }, { value: '门店销售' }, { value: '公对公' }] },
      { name: '收入账户', type: 'SingleSelect', items: [{ value: '广州彩次元' }, { value: '广东北斗' }, { value: '华个人帐' }, { value: '售后换新' }, { value: '门店销售' }] },
      { name: '收款状态', type: 'SingleSelect', items: [{ value: '已收款' }, { value: '未收款' }] },
      { name: '操作人', type: 'MultiLineText' },
      { name: '备注', type: 'MultiLineText' },
      { name: '创建时间', type: 'CreatedTime' }
    ],
    Views: [
      { name: '出库列表', type: 'Grid' },
      { name: '按客户', type: 'Kanban' }
    ]
  });
  console.log('✅ 出库记录已创建:', outboundSheet.id);

  // ========== 4. 创建「库存总览」 ==========
  var inventorySheet = Application.Sheet.CreateSheet({
    Name: '库存总览',
    Fields: [
      { name: 'SN', type: 'MultiLineText' },
      { name: '编码', type: 'MultiLineText' },
      { name: '名称', type: 'MultiLineText' },
      { name: '仓位', type: 'SingleSelect', items: [{ value: '广州百脑汇仓' }, { value: '深圳大我仓' }] },
      { name: '进价', type: 'Currency' },
      { name: '状态', type: 'SingleSelect', items: [{ value: '在库' }, { value: '已出库' }, { value: '调货中' }] },
      { name: '入库日期', type: 'Date' },
      { name: '入库单号', type: 'MultiLineText' },
      { name: '出库日期', type: 'Date' },
      { name: '出库单号', type: 'MultiLineText' },
      { name: '客户', type: 'MultiLineText' },
      { name: '售价', type: 'Currency' },
      { name: '操作人', type: 'MultiLineText' }
    ],
    Views: [
      { name: '库存列表', type: 'Grid' },
      { name: '按仓位', type: 'Kanban' }
    ]
  });
  console.log('✅ 库存总览已创建:', inventorySheet.id);

  // ========== 5. 创建「配置表」 ==========
  var configSheet = Application.Sheet.CreateSheet({
    Name: '系统配置',
    Fields: [
      { name: '配置项', type: 'MultiLineText' },
      { name: '配置值', type: 'MultiLineText' }
    ],
    Views: [
      { name: '配置列表', type: 'Grid' }
    ]
  });
  console.log('✅ 系统配置已创建:', configSheet.id);

  // 写入配置数据
  Application.Record.CreateRecords({
    SheetId: configSheet.id,
    Records: [
      { fields: { 配置项: '仓位列表', 配置值: '广州百脑汇仓,深圳大我仓' } },
      { fields: { 配置项: '采购账户列表', 配置值: '广州彩次元,广东北斗,华个人帐,售后换新,门店销售' } },
      { fields: { 配置项: '客户列表', 配置值: 'PDD彩次元,JD个人,TB个人,XY个人,DY个人,门店销售,公对公' } },
      { fields: { 配置项: '供应商列表', 配置值: '深圳大我,深圳国阅,深圳掌阅,广州格凡' } },
      { fields: { 配置项: '收入账户列表', 配置值: '广州彩次元,广东北斗,华个人帐,售后换新,门店销售' } },
    ]
  });

  console.log('========================================');
  console.log('🎉 出入库系统初始化完成！');
  console.log('物料表 ID:', materialSheet.id);
  console.log('入库记录 ID:', inboundSheet.id);
  console.log('出库记录 ID:', outboundSheet.id);
  console.log('库存总览 ID:', inventorySheet.id);
  console.log('系统配置 ID:', configSheet.id);
  console.log('========================================');
}

main();
