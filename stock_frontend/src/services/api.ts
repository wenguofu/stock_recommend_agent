/**
 * API服务 - 与后端通信
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';

export interface StockRealtime {
  code: string;
  name: string;
  current_price: number;
  change_percent: number;
  volume: number;
  amount: number;
  high: number;
  low: number;
  open: number;
  yesterday_close: number;
  turnover_rate?: number; // 换手率
}

export interface StockComprehensive {
  code: string;
  realtime: StockRealtime;
  daily_count: number;
  indicators?: any;
  money_flow?: any;
  fundamental?: any;
  industry_comparison?: any;
}

export interface WatchlistItem {
  id: number;
  code: string;
  name: string;
  cost_price?: number | null;
  shares?: number | null;
  sort_order: number;
}

export interface Agent {
  id: number;
  name: string;
  type: 'default' | 'intraday_t' | 'review';
  prompt: string;
  enabled: boolean;
  ai_provider: string | null;
  model: string | null;
  sort_order: number;
}

export interface AnalysisResult {
  analysis: string;
  agent_name: string;
  agent_type: string;
  timestamp: string;
  recommendation?: {
    buy_price: number;
    sell_price: number;
  };
}

export interface DebateStep {
  phase: 'analysis' | 'debate';
  round: number;
  agent_id: number;
  agent_name: string;
  content: string;
  timestamp: string;
}

export interface DebateResult {
  steps: DebateStep[];
  report_md: string;
  analysis_rounds: number;
  debate_rounds: number;
}

export interface DebateJobStatus {
  job_id: string;
  code: string;
  name: string;
  agent_ids: number[];
  analysis_rounds: number;
  debate_rounds: number;
  meta?: {
    mode?: string;
    codes?: string[];
    decision_agent_id?: number;
  };
  status: 'queued' | 'running' | 'completed' | 'failed' | 'canceled';
  progress: number;
  progress_detail?: string[];
  steps: DebateStep[];
  report_md: string;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface StrategySummary {
  id: number;
  name: string;
  description: string;
  category: string;
  enabled: boolean;
  sort_order: number;
  created_at: string;
  agent_count: number;
}

export interface StrategyDetail extends StrategySummary {
  doc_md: string;
  agent_configs: Array<{
    name: string;
    type: string;
    sort_order: number;
    prompt: string;
  }>;
}

class StockAPI {
  private baseURL: string;

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  getBaseURL() {
    return this.baseURL;
  }

  setBaseURL(url: string) {
    this.baseURL = url;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    return response.json();
  }

  // 数据获取API
  async getRealtime(code: string): Promise<StockRealtime> {
    const response = await this.request<any>(`/api/sina/realtime/${code}`);
    // 后端返回格式可能是 { data: {...} } 或直接返回数据
    return response.data || response;
  }

  async getComprehensive(code: string): Promise<StockComprehensive> {
    const response = await this.request<any>(`/api/sina/comprehensive_with_indicators/${code}`);
    // 后端返回格式可能是 { data: {...} } 或直接返回数据
    return response.data || response;
  }

  async getSentiment(code: string, days: number = 7): Promise<any> {
    return this.request(`/api/sentiment/all/${code}?days=${days}&latest=10&hot=10`);
  }

  // 自选股API
  async getWatchlist(): Promise<WatchlistItem[]> {
    const data = await this.request<{ success: boolean; data: WatchlistItem[] }>('/api/watchlist');
    return data.data;
  }

  async addWatchlist(code: string, name?: string, cost_price?: number | null, shares?: number | null): Promise<WatchlistItem> {
    const data = await this.request<{ success: boolean; data: WatchlistItem }>('/api/watchlist', {
      method: 'POST',
      body: JSON.stringify({ code, name, cost_price, shares }),
    });
    return data.data;
  }

  async updateWatchlistPosition(code: string, cost_price?: number | null, shares?: number | null): Promise<WatchlistItem> {
    const data = await this.request<{ success: boolean; data: WatchlistItem }>(`/api/watchlist/${code}/position`, {
      method: 'PUT',
      body: JSON.stringify({ cost_price, shares }),
    });
    return data.data;
  }

  async removeWatchlist(code: string): Promise<boolean> {
    const data = await this.request<{ success: boolean }>(`/api/watchlist/${code}`, {
      method: 'DELETE',
    });
    return data.success;
  }

  async updateWatchlistOrder(orders: Array<{ code: string; sort_order: number }>): Promise<boolean> {
    const data = await this.request<{ success: boolean }>('/api/watchlist/order', {
      method: 'POST',
      body: JSON.stringify({ orders }),
    });
    return data.success;
  }

  // 配置API
  async getConfig(key: string): Promise<string | null> {
    const data = await this.request<{ success: boolean; data: Record<string, string> }>(`/api/config/${key}`);
    return data.data[key] || null;
  }

  async getAllConfigs(): Promise<Record<string, string>> {
    const data = await this.request<{ success: boolean; data: Record<string, string> }>('/api/config');
    return data.data;
  }

  async setConfig(key: string, value: string): Promise<boolean> {
    const data = await this.request<{ success: boolean }>(`/api/config/${key}`, {
      method: 'POST',
      body: JSON.stringify({ value }),
    });
    return data.success;
  }

  // Agent API
  async getAgents(enabledOnly: boolean = false): Promise<Agent[]> {
    const data = await this.request<{ success: boolean; data: Agent[] }>(
      `/api/agents?enabled_only=${enabledOnly}`
    );
    return data.data;
  }

  async createAgent(agent: Partial<Agent>): Promise<number> {
    const data = await this.request<{ success: boolean; data: { id: number } }>('/api/agents', {
      method: 'POST',
      body: JSON.stringify(agent),
    });
    return data.data.id;
  }

  async updateAgent(id: number, updates: Partial<Agent>): Promise<boolean> {
    const data = await this.request<{ success: boolean }>(`/api/agents/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
    return data.success;
  }

  async deleteAgent(id: number): Promise<boolean> {
    const data = await this.request<{ success: boolean }>(`/api/agents/${id}`, {
      method: 'DELETE',
    });
    return data.success;
  }

  // AI分析API
  async analyzeStock(code: string, agentId: number, useCache: boolean = true): Promise<AnalysisResult> {
    const data = await this.request<{ success: boolean; data: AnalysisResult }>(`/api/ai/analyze/${code}`, {
      method: 'POST',
      body: JSON.stringify({ agent_id: agentId, use_cache: useCache }),
    });
    return data.data;
  }

  async debateStock(
    code: string,
    agentIds: number[],
    analysisRounds: number = 3,
    debateRounds: number = 3
  ): Promise<DebateResult> {
    const data = await this.request<{ success: boolean; data: DebateResult }>(`/api/ai/debate/${code}`, {
      method: 'POST',
      body: JSON.stringify({
        agent_ids: agentIds,
        analysis_rounds: analysisRounds,
        debate_rounds: debateRounds,
      }),
    });
    return data.data;
  }

  async startDebateJob(
    code: string,
    agentIds: number[],
    analysisRounds: number = 3,
    debateRounds: number = 3
  ): Promise<{ job_id: string; name: string }> {
    const data = await this.request<{ success: boolean; data: { job_id: string; name: string } }>(`/api/ai/debate/start/${code}`, {
      method: 'POST',
      body: JSON.stringify({
        agent_ids: agentIds,
        analysis_rounds: analysisRounds,
        debate_rounds: debateRounds,
      }),
    });
    return data.data;
  }

  async getDebateJobStatus(jobId: string): Promise<DebateJobStatus> {
    const data = await this.request<{ success: boolean; data: DebateJobStatus }>(`/api/ai/debate/status/${jobId}`);
    return data.data;
  }

  async listDebateJobs(status?: string, limit: number = 50): Promise<DebateJobStatus[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    params.append('limit', String(limit));
    const data = await this.request<{ success: boolean; data: DebateJobStatus[] }>(`/api/ai/debate/jobs?${params.toString()}`);
    return data.data;
  }

  async startMultiSelectDebate(
    codes: string[],
    agentIds: number[],
    analysisRounds: number = 2,
    debateRounds: number = 1
  ): Promise<{ job_id: string; name: string }> {
    const data = await this.request<{ success: boolean; data: { job_id: string; name: string } }>('/api/ai/debate/start_multi', {
      method: 'POST',
      body: JSON.stringify({
        codes,
        agent_ids: agentIds,
        analysis_rounds: analysisRounds,
        debate_rounds: debateRounds,
      }),
    });
    return data.data;
  }

  async getStrongStocks(limitTime: string): Promise<any> {
    return this.request(`/api/strategy/strong_stocks?limit_time=${encodeURIComponent(limitTime)}`);
  }

  async stopDebateJob(jobId: string): Promise<boolean> {
    const data = await this.request<{ success: boolean }>(`/api/ai/debate/stop/${jobId}`, {
      method: 'POST',
    });
    return data.success;
  }

  async deleteDebateJob(jobId: string): Promise<boolean> {
    const data = await this.request<{ success: boolean }>(`/api/ai/debate/delete/${jobId}`, {
      method: 'DELETE',
    });
    return data.success;
  }

  // 策略库API
  async getStrategies(category?: string, enabledOnly?: boolean): Promise<{ strategies: StrategySummary[]; count: number }> {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (enabledOnly) params.append('enabled_only', 'true');
    return this.request(`/api/strategies?${params.toString()}`);
  }

  async getStrategyDetail(id: number): Promise<StrategyDetail> {
    return this.request(`/api/strategies/${id}`);
  }

  async createStrategy(data: { name: string; description?: string; category?: string; doc_md?: string; agent_configs?: any[]; sort_order?: number }): Promise<any> {
    return this.request('/api/strategies', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateStrategy(id: number, data: any): Promise<any> {
    return this.request(`/api/strategies/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteStrategy(id: number): Promise<any> {
    return this.request(`/api/strategies/${id}`, {
      method: 'DELETE',
    });
  }

  async applyStrategy(id: number): Promise<{ message: string; results: any[]; count: number }> {
    return this.request(`/api/strategies/${id}/apply`, {
      method: 'POST',
    });
  }

  async runStrategy(id: number, codes: string[], analysisRounds: number = 2, debateRounds: number = 1): Promise<any> {
    return this.request(`/api/strategies/${id}/run`, {
      method: 'POST',
      body: JSON.stringify({ codes, analysis_rounds: analysisRounds, debate_rounds: debateRounds }),
    });
  }

  // AI服务工具API
  async getAIModels(provider: string, apiKey?: string): Promise<string[]> {
    const params = new URLSearchParams({ provider });
    if (apiKey) {
      params.append('api_key', apiKey);
    }
    const data = await this.request<{ success: boolean; data: string[] }>(`/api/ai/models?${params.toString()}`);
    return data.data;
  }

  async testAIConnection(provider: string, apiKey: string, model?: string): Promise<{ success: boolean; message: string; response?: string }> {
    const data = await this.request<{ success: boolean; message: string; response?: string }>('/api/ai/test', {
      method: 'POST',
      body: JSON.stringify({ provider, api_key: apiKey, model }),
    });
    return data;
  }

  // 盯盘任务 API
  async listTasks(): Promise<any[]> {
    const data = await this.request<{ success: boolean; data: any[] }>('/api/tasks');
    return data.data;
  }

  async createTask(task: { name: string; task_type: string; codes: string[]; schedule: string; agent_ids?: number[]; config?: any; enabled?: boolean }): Promise<{ id: number }> {
    const data = await this.request<{ success: boolean; data: { id: number } }>('/api/tasks', {
      method: 'POST', body: JSON.stringify(task),
    });
    return data.data;
  }

  async updateTask(id: number, updates: any): Promise<boolean> {
    const data = await this.request<{ success: boolean }>(`/api/tasks/${id}`, {
      method: 'PUT', body: JSON.stringify(updates),
    });
    return data.success;
  }

  async deleteTask(id: number): Promise<boolean> {
    const data = await this.request<{ success: boolean }>(`/api/tasks/${id}`, { method: 'DELETE' });
    return data.success;
  }

  async triggerTask(id: number): Promise<boolean> {
    const data = await this.request<{ success: boolean }>(`/api/tasks/${id}/trigger`, { method: 'POST' });
    return data.success;
  }

  async listTaskLogs(id: number, limit: number = 20): Promise<any[]> {
    const data = await this.request<{ success: boolean; data: any[] }>(`/api/tasks/${id}/logs?limit=${limit}`);
    return data.data;
  }

  async getAlerts(limit: number = 20): Promise<any[]> {
    const data = await this.request<{ success: boolean; data: any[] }>(`/api/tasks/alerts?limit=${limit}`);
    return data.data;
  }

  // 板块数据 API
  async listSectors(): Promise<string[]> {
    const data = await this.request<{ success: boolean; data: string[] }>('/api/sectors');
    return data.data;
  }

  async getSectorStocks(sectorName: string): Promise<{ code: string; name: string }[]> {
    const data = await this.request<{ success: boolean; stocks: { code: string; name: string }[] }>(`/api/sectors/${encodeURIComponent(sectorName)}`);
    return data.stocks;
  }

  async getSectorPerformance(): Promise<any[]> {
    const data = await this.request<{ success: boolean; data: any[] }>('/api/sectors/performance');
    return data.data;
  }

  async getMarketOutlook(): Promise<any> {
    const data = await this.request<any>('/api/market/outlook');
    return data;
  }

  // ═══════════ 预测 API ═══════════

  async runForecast(payload: {
    code: string; strategy: string; params: Record<string, any>; forecast_days?: number;
  }): Promise<any> {
    return this.request('/api/forecast', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  // ═══════════ 回测 API ═══════════

  async getBacktestPresets(): Promise<any[]> {
    const data = await this.request<{ presets: any[] }>('/api/backtest/presets');
    return data.presets;
  }

  async runBacktest(payload: {
    code: string; strategy: string; params: Record<string, any>;
    initial_capital?: number; start_date?: string; end_date?: string;
  }): Promise<any> {
    return this.request('/api/backtest/run', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  // ═══════════ 买卖计划 API ═══════════

  async getPlans(accountId: number, code?: string): Promise<any[]> {
    const params = code ? `?code=${code}` : '';
    const data = await this.request<{ plans: any[] }>(`/api/paper/plans/${accountId}${params}`);
    return data.plans;
  }

  async createPlan(accountId: number, payload: any): Promise<any> {
    const data = await this.request<any>(`/api/paper/plans/${accountId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    return data.plan;
  }

  async batchCreatePlans(accountId: number, code: string, name: string, currentPrice?: number): Promise<any> {
    const data = await this.request<any>(`/api/paper/plans/${accountId}/batch`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, name, current_price: currentPrice }),
    });
    return data;
  }

  async updatePlanStatus(planId: number, status: string): Promise<void> {
    await this.request(`/api/paper/plans/${planId}/status`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }),
    });
  }
}

export const stockAPI = new StockAPI();

