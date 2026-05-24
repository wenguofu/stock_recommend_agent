import React from 'react';

interface MoneyFlowItem {
  label: string;
  value: number | null;
  ratio?: number | null;
  unit: string;
}

interface MoneyFlowData {
  main_net_inflow?: number | null;
  main_net_ratio?: number | null;
  super_large_net_inflow?: number | null;
  super_large_net_ratio?: number | null;
  large_net_inflow?: number | null;
  large_net_ratio?: number | null;
  medium_net_inflow?: number | null;
  small_net_inflow?: number | null;
}

interface Props {
  moneyFlow: MoneyFlowData;
}

function MoneyFlowRow({ label, value, ratio, unit }: MoneyFlowItem) {
  if (value == null) return null;
  const isPositive = value >= 0;
  return (
    <div>
      <div className="text-sm text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`text-lg font-semibold ${isPositive ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
        {isPositive ? '+' : ''}{value.toFixed(2)}{unit}
      </div>
      {ratio != null && (
        <div className="text-xs text-gray-400 mt-1">占比: {ratio.toFixed(2)}%</div>
      )}
    </div>
  );
}

export default function MoneyFlowPanel({ moneyFlow }: Props) {
  const items: MoneyFlowItem[] = [
    { label: '主力净流入', value: moneyFlow.main_net_inflow ?? null, ratio: moneyFlow.main_net_ratio ?? null, unit: '万' },
    { label: '超大单净流入', value: moneyFlow.super_large_net_inflow ?? null, ratio: moneyFlow.super_large_net_ratio ?? null, unit: '万' },
    { label: '大单净流入', value: moneyFlow.large_net_inflow ?? null, ratio: moneyFlow.large_net_ratio ?? null, unit: '万' },
    { label: '中单净流入', value: moneyFlow.medium_net_inflow ?? null, ratio: null, unit: '万' },
    { label: '小单净流入', value: moneyFlow.small_net_inflow ?? null, ratio: null, unit: '万' },
  ];

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">今日资金流向</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {items.map((item, idx) => (
          <MoneyFlowRow key={idx} {...item} />
        ))}
      </div>
    </div>
  );
}
