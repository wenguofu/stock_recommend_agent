import { useState, useEffect } from 'react';
import { stockAPI } from '../services/api';

const SCHEDULE_OPTIONS = [
  { value: 'every_5m', label: '每5分钟' },
  { value: 'every_15m', label: '每15分钟' },
  { value: 'every_30m', label: '每30分钟' },
  { value: 'every_1h', label: '每小时' },
  { value: 'every_4h', label: '每4小时' },
];

const TASK_TYPE_OPTIONS = [
  { value: 'price_alert', label: '📊 价格提醒', desc: '监控股票涨跌幅，超过阈值时触发提醒' },
  { value: 'ai_analysis', label: '🤖 AI分析', desc: '定时运行AI多Agent分析，生成研究报告' },
];

export default function Tasks() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [showAlerts, setShowAlerts] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [logs, setLogs] = useState<Record<number, any[]>>({});
  const [expandedLog, setExpandedLog] = useState<number | null>(null);

  // 表单
  const [formName, setFormName] = useState('');
  const [formType, setFormType] = useState('price_alert');
  const [formCodes, setFormCodes] = useState('');
  const [formSchedule, setFormSchedule] = useState('every_15m');
  const [formPriceUp, setFormPriceUp] = useState('');
  const [formPriceDown, setFormPriceDown] = useState('');

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const data = await stockAPI.listTasks();
      setTasks(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTasks(); }, []);

  const fetchAlerts = async () => {
    const data = await stockAPI.getAlerts();
    setAlerts(data);
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 10000);
    return () => clearInterval(interval);
  }, []);

  const openCreate = () => {
    setEditId(null);
    setFormName(''); setFormType('price_alert'); setFormCodes('');
    setFormSchedule('every_15m'); setFormPriceUp(''); setFormPriceDown('');
    setShowForm(true);
  };

  const openEdit = (t: any) => {
    setEditId(t.id);
    setFormName(t.name);
    setFormType(t.task_type);
    setFormCodes((t.codes || []).join(','));
    setFormSchedule(t.schedule);
    setFormPriceUp(t.config?.price_up || '');
    setFormPriceDown(t.config?.price_down || '');
    setShowForm(true);
  };

  const handleSave = async () => {
    const codes = formCodes.split(',').map((c) => c.trim()).filter(Boolean);
    const config: any = {};
    if (formPriceUp) config.price_up = parseFloat(formPriceUp);
    if (formPriceDown) config.price_down = parseFloat(formPriceDown);

    const task = {
      name: formName || '未命名任务',
      task_type: formType,
      codes,
      schedule: formSchedule,
      config,
    };

    if (editId) {
      await stockAPI.updateTask(editId, task);
    } else {
      await stockAPI.createTask(task);
    }
    setShowForm(false);
    fetchTasks();
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确认删除此任务？')) return;
    await stockAPI.deleteTask(id);
    fetchTasks();
  };

  const handleTrigger = async (id: number) => {
    await stockAPI.triggerTask(id);
    fetchTasks();
  };

  const toggleLogs = async (taskId: number) => {
    if (expandedLog === taskId) {
      setExpandedLog(null);
      return;
    }
    setExpandedLog(taskId);
    const data = await stockAPI.listTaskLogs(taskId);
    setLogs((prev) => ({ ...prev, [taskId]: data }));
  };

  const getScheduleLabel = (v: string) => SCHEDULE_OPTIONS.find((o) => o.value === v)?.label || v;
  const getTypeLabel = (v: string) => TASK_TYPE_OPTIONS.find((o) => o.value === v)?.label || v;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">📋 盯盘任务</h1>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          + 新建任务
        </button>
      </div>

      {/* 实时提醒面板 */}
      {alerts.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-yellow-300 dark:border-yellow-600 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-700">
            <div className="flex items-center gap-2">
              <span className="text-lg">🔔</span>
              <h2 className="font-semibold text-yellow-800 dark:text-yellow-300">实时盯盘提醒</h2>
              <span className="text-xs bg-yellow-200 dark:bg-yellow-700 text-yellow-800 dark:text-yellow-300 px-2 py-0.5 rounded-full">{alerts.length}条</span>
            </div>
            <button onClick={() => setShowAlerts(!showAlerts)} className="text-sm text-yellow-600 dark:text-yellow-400 hover:underline">
              {showAlerts ? '收起' : '展开'}
            </button>
          </div>
          {showAlerts && (
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {alerts.map((a, i) => (
                <div key={i} className="px-4 py-3 flex items-start gap-3 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                  <span className={a.type === 'price_up' ? 'text-red-500 text-lg' : 'text-green-500 text-lg'}>
                    {a.type === 'price_up' ? '📈' : '📉'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{a.message}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      {new Date(a.timestamp).toLocaleString()} · 任务: {a.task_name}
                    </div>
                  </div>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded self-center ${a.type === 'price_up' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                    {a.type === 'price_up' ? '+' : ''}{a.value?.toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 任务列表 */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">加载中...</div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 mb-4">暂无盯盘任务</p>
          <button onClick={openCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            创建第一个任务
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {tasks.map((t) => (
            <div key={t.id} className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="p-4 flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="font-semibold text-gray-900 dark:text-white">{t.name}</h3>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">
                      {getTypeLabel(t.task_type)}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${t.enabled ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-gray-100 dark:bg-gray-700 text-gray-500'}`}>
                      {t.enabled ? '启用' : '停用'}
                    </span>
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400 space-y-0.5">
                    <div>📈 {(t.codes || []).join(', ')}</div>
                    <div>⏱ {getScheduleLabel(t.schedule)}</div>
                    {t.last_run && <div>🕐 上次: {new Date(t.last_run).toLocaleString()}</div>}
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-4">
                  <button onClick={() => handleTrigger(t.id)} className="px-3 py-1.5 text-xs bg-green-600 text-white rounded hover:bg-green-700">▶ 执行</button>
                  <button onClick={() => stockAPI.updateTask(t.id, { enabled: !t.enabled }).then(() => fetchTasks())}
                    className="px-3 py-1.5 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600">
                    {t.enabled ? '暂停' : '启用'}
                  </button>
                  <button onClick={() => openEdit(t)} className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">编辑</button>
                  <button onClick={() => handleDelete(t.id)} className="px-3 py-1.5 text-xs bg-red-600 text-white rounded hover:bg-red-700">删除</button>
                  <button onClick={() => toggleLogs(t.id)} className="px-3 py-1.5 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600">
                    {expandedLog === t.id ? '收起日志' : '日志'}
                  </button>
                </div>
              </div>
              {/* 日志展开 */}
              {expandedLog === t.id && (
                <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 p-4">
                  {(!logs[t.id] || logs[t.id].length === 0) ? (
                    <p className="text-sm text-gray-500">暂无执行记录</p>
                  ) : (
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {logs[t.id].map((log: any) => (
                        <div key={log.id} className="flex items-center justify-between p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 text-sm">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded ${log.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                            {log.status}
                          </span>
                          <span className="text-gray-500">{new Date(log.started_at).toLocaleString()}</span>
                          <span className="text-gray-600">{log.triggered_count > 0 ? `⚠ ${log.triggered_count}条提醒` : '无触发'}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 创建/编辑弹窗 */}
      {showForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setShowForm(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              {editId ? '编辑任务' : '新建盯盘任务'}
            </h2>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">任务名称</label>
              <input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="如：蓝思科技盯盘"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white" />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">任务类型</label>
              <select value={formType} onChange={(e) => setFormType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white">
                {TASK_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <p className="text-xs text-gray-500 mt-1">{TASK_TYPE_OPTIONS.find((o) => o.value === formType)?.desc}</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">股票代码（多个用逗号分隔）</label>
              <input value={formCodes} onChange={(e) => setFormCodes(e.target.value)} placeholder="如：300433, AAPL, SE"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white" />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">执行频率</label>
              <select value={formSchedule} onChange={(e) => setFormSchedule(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white">
                {SCHEDULE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            {formType === 'price_alert' && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">涨幅提醒（%）</label>
                  <input type="number" value={formPriceUp} onChange={(e) => setFormPriceUp(e.target.value)} placeholder="如：5"
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">跌幅提醒（%）</label>
                  <input type="number" value={formPriceDown} onChange={(e) => setFormPriceDown(e.target.value)} placeholder="如：3"
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white" />
                </div>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button onClick={() => setShowForm(false)} className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">取消</button>
              <button onClick={handleSave} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                {editId ? '保存修改' : '创建任务'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
