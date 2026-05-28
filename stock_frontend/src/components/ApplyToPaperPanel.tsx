import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, Select, Button, Alert, Tag, Space, Typography, Spin } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

const { Text, Title } = Typography;

interface ApplyToPaperPanelProps {
  codes: string[];
  jobName: string;
  strategyRunId: string;
}

interface PaperAccount {
  id: number;
  name: string;
  initial_capital: number;
}

export default function ApplyToPaperPanel({ codes, jobName, strategyRunId }: ApplyToPaperPanelProps) {
  const queryClient = useQueryClient();
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [showResult, setShowResult] = useState<{ success: boolean; message: string } | null>(null);

  const { data: accounts, isLoading } = useQuery({
    queryKey: ["paper-accounts"],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts`);
      if (!r.ok) throw new Error("获取模拟盘列表失败");
      const d = await r.json();
      return d.accounts as PaperAccount[];
    },
  });

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (!selectedAccountId) throw new Error("请选择模拟盘账户");

      const signals = codes.map((code) => ({
        code,
        name: "",
        direction: "buy",
        price: 0,
        quantity: 100,
        note: `策略信号: ${jobName}`,
      }));

      // Try to get real-time prices first
      const signalsWithPrices = await Promise.all(
        signals.map(async (s) => {
          try {
            const r = await fetch(`${API_BASE}/api/sina/realtime/${s.code}`);
            if (r.ok) {
              const data = await r.json();
              return {
                ...s,
                name: data.name || "",
                price: data.current_price || 0,
              };
            }
          } catch {}
          return s;
        })
      );

      const r = await fetch(`${API_BASE}/api/strategy/apply_to_paper`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_id: selectedAccountId,
          signals: signalsWithPrices,
          strategy_run_id: strategyRunId,
        }),
      });
      const result = await r.json();
      if (!r.ok) throw new Error(result.error || "应用失败");
      return result;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["paper-accounts"] });
      setShowResult({
        success: true,
        message: `成功执行 ${data.executed} 个信号${data.failed > 0 ? `，${data.failed} 个失败` : ""}`,
      });
    },
    onError: (error) => {
      setShowResult({ success: false, message: (error as Error).message });
    },
  });

  if (isLoading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin />
        </div>
      </Card>
    );
  }

  if (!accounts?.length) {
    return (
      <Card
        title={<Space><Text strong>📊 应用到模拟盘</Text></Space>}
        style={{ marginTop: 16 }}
      >
        <Text type="secondary">还没有创建模拟盘账户，请先在模拟盘页面创建一个。</Text>
        <div style={{ marginTop: 16 }}>
          <Button type="primary" href="/paper">前往模拟盘</Button>
        </div>
      </Card>
    );
  }

  return (
    <Card
      title={<Space><Text strong>📊 应用到模拟盘</Text></Space>}
      style={{ marginTop: 16 }}
    >
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        将策略分析结果中推荐的股票作为买入信号应用到模拟盘账户
      </Text>

      {/* Target Stocks */}
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>目标股票 ({codes.length} 只):</Text>
        <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {codes.map((code) => (
            <Tag key={code} color="blue">{code}</Tag>
          ))}
        </div>
      </div>

      {/* Account Selector */}
      <Space style={{ width: '100%', marginBottom: 16 }}>
        <Select
          value={selectedAccountId ?? undefined}
          onChange={(val) => setSelectedAccountId(val ?? null)}
          placeholder="-- 选择模拟盘账户 --"
          style={{ flex: 1, minWidth: 250 }}
          options={accounts.map((a) => ({
            label: `${a.name} (初始 ${a.initial_capital.toLocaleString()})`,
            value: a.id,
          }))}
        />
        <Button
          type="primary"
          onClick={() => applyMutation.mutate()}
          disabled={!selectedAccountId || applyMutation.isPending}
          loading={applyMutation.isPending}
        >
          {applyMutation.isPending ? "执行中..." : "应用信号"}
        </Button>
      </Space>

      {/* Result */}
      {showResult && (
        <Alert
          type={showResult.success ? "success" : "error"}
          message={showResult.message}
          showIcon
          action={
            <Space size="small">
              {showResult.success && (
                <Button
                  type="link"
                  size="small"
                  onClick={() => window.open(`/paper/${selectedAccountId}`, "_self")}
                >
                  查看账户
                </Button>
              )}
              <Button
                type="link"
                size="small"
                onClick={() => setShowResult(null)}
              >
                关闭
              </Button>
            </Space>
          }
        />
      )}

      {/* Errors detail */}
      {applyMutation.data?.errors?.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }} strong>失败详情:</Text>
          {applyMutation.data.errors.map((e: any, i: number) => (
            <div key={i} style={{ fontSize: 12 }}>
              <Text type="secondary">#{e.index} {e.code}: {e.error}</Text>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
