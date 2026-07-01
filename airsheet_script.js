/**
 * 出入库管理系统 - WPS 智能表格 AirScript 1.0 脚本
 * 使用数据表 API (Record.CreateRecords / GetRecords)
 * 
 * 使用方法：
 * 1. 在智能表格中创建 AirScript 1.0 脚本
 * 2. 粘贴此代码，Ctrl+S 保存
 * 3. 生成 Token + webhook
 */
var request = {
  action: '',
  sheet: '',
  fields: null,
  filter: null,
  id: '',
};

if (typeof Context !== 'undefined' && Context.argv) {
  request.action = Context.argv.action || '';
  request.sheet = Context.argv.sheet || '';
  request.fields = Context.argv.fields || null;
  request.filter = Context.argv.filter || null;
  request.id = Context.argv.id || '';
}

var response = { success: false, data: null, message: '' };

try {
  if (!request.action) {
    response.message = 'action 参数不能为空';
  } else if (!request.sheet) {
    response.message = 'sheet 参数不能为空';
  } else {
    var sheet = Application.Sheets.Item(request.sheet);
    
    switch (request.action) {
      case 'create':
        response.data = create(sheet);
        response.success = true;
        response.message = '创建成功';
        break;
      case 'read':
        response.data = read(sheet);
        response.success = true;
        response.message = '查询成功';
        break;
      case 'readAll':
        response.data = readAll(sheet);
        response.success = true;
        response.message = '查询成功';
        break;
      case 'update':
        response.data = update(sheet);
        response.success = true;
        response.message = '更新成功';
        break;
      case 'delete':
        response.data = del(sheet);
        response.success = true;
        response.message = '删除成功';
        break;
      case 'deleteAll':
        response.data = deleteAll(sheet);
        response.success = true;
        response.message = '清空成功';
        break;
      case 'count':
        response.data = count(sheet);
        response.success = true;
        break;
      default:
        response.message = '未知操作: ' + request.action + '，支持: create, read, readAll, update, delete, deleteAll, count';
    }
  }
} catch (e) {
  response.success = false;
  response.message = e.message || String(e);
}

function create(sheet) {
  return sheet.Record.CreateRecords({
    Records: [{ fields: request.fields }]
  });
}

function read(sheet) {
  return sheet.Record.GetRecords({
    Filter: request.filter
  });
}

function readAll(sheet) {
  var all = [];
  var offset = null;
  var count = 0;
  while (count < 20) {  // 最多 20 页，防止死循环
    var result = sheet.Record.GetRecords({ Offset: offset });
    all = all.concat(result.records);
    offset = result.offset;
    if (!offset) break;
    count++;
  }
  return all;
}

function update(sheet) {
  var records = [];
  if (request.filter) {
    var result = sheet.Record.GetRecords({ Filter: request.filter });
    records = result.records;
  } else if (request.id) {
    records = [{ id: request.id }];
  }
  if (records.length === 0) {
    return { updated: 0, message: '没有找到匹配的记录' };
  }
  return sheet.Record.UpdateRecords({
    Records: records.map(function(r) {
      return { id: r.id, fields: request.fields };
    })
  });
}

function del(sheet) {
  var records = [];
  if (request.filter) {
    var result = sheet.Record.GetRecords({ Filter: request.filter });
    records = result.records;
  } else if (request.id) {
    records = [{ id: request.id }];
  }
  if (records.length === 0) {
    return { deleted: 0, message: '没有找到匹配的记录' };
  }
  return sheet.Record.DeleteRecords({
    RecordIds: records.map(function(r) { return r.id; })
  });
}

function deleteAll(sheet) {
  var allRecords = readAll(sheet);
  if (allRecords.length === 0) return { deleted: 0 };
  var ids = allRecords.map(function(r) { return r.id; });
  // 分批删除，每批 100 条
  var deleted = 0;
  for (var i = 0; i < ids.length; i += 100) {
    var batch = ids.slice(i, i + 100);
    sheet.Record.DeleteRecords({ RecordIds: batch });
    deleted += batch.length;
  }
  return { deleted: deleted };
}

function count(sheet) {
  var all = readAll(sheet);
  return { count: all.length };
}

return response;
