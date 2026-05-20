import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface TradeModalProps {
  accountId: number;
  onClose: () => void;
  onSuccess: () => void;
}

export default function TradeModal({ accountId, onClose, onSuccess }: TradeModalProps) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [direction, setDirection] = useState<"buy" | "sell">("buy");
  const [price, setPrice] = useState("");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [isEtfReplaced, setIsEtfReplaced] = useState(false);

  const handleFetchStock = async () => {
    const trimmed = code.trim();
    if (!/^\d{6}$/.test(trimmed)) {
      setError("请输入6位A股代码");
      return;
    }
    setFetching(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/sina/realtime/${trimmed}`);
      if (!res.ok) throw new Error("获取股票信息失败");
      const data = await res.json();
      setName(data.name || "");
      setPrice(String(data.current_price || ""));
      setIsEtfReplaced(trimmed.startsWith("688"));
    } catch (e) {
      setError("获取股票信息失败，请检查代码是否正确");
    } finally {
      setFetching(false);
    }
  };

  const handleSubmit = async () => {
    if (!confirm) {
      setConfirm(true);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: code.trim(),
          name,
          direction,
          price: parseFloat(price),
          quantity: parseInt(quantity),
          note,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "下单失败");
      onSuccess();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setConfirm(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-md mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">
            {confirm ? "确认交易" : "手动交易"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm">
            {error}
          </div>
        )}

        {isEtfReplaced && !confirm && (
          <div className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg text-yellow-700 dark:text-yellow-400 text-sm">
            科创板代码(688开头)将自动替换为对应ETF进行模拟交易
          </div>
        )}

        {!confirm ? (
          <div className="space-y-4">
            {/* Stock Code */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">股票代码</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="6位A股代码"
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={handleFetchStock}
                  disabled={fetching || code.length !== 6}
                  className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors"
                >
                  {fetching ? "..." : "查询"}
                </button>
              </div>
            </div>

            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">股票名称</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="自动填充或手动输入"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Direction */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">方向</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setDirection("buy")}
                  className={`flex-1 py-2 rounded-lg font-medium transition-colors ${direction === "buy" ? "bg-red-500 text-white" : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"}`}
                >
                  买入
                </button>
                <button
                  onClick={() => setDirection("sell")}
                  className={`flex-1 py-2 rounded-lg font-medium transition-colors ${direction === "sell" ? "bg-green-500 text-white" : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"}`}
                >
                  卖出
                </button>
              </div>
            </div>

            {/* Price */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">价格</label>
              <input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                step="0.01"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Quantity */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">数量（股）</label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                min="100"
                step="100"
                placeholder="A股最小100股"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Note */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">备注（可选）</label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={!code || !price || !quantity}
              className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
            >
              下一步 - 确认交易
            </button>
          </div>
        ) : (
          /* Confirmation Screen */
          <div className="space-y-4">
            <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-500">股票</span>
                <span className="font-medium">{name} ({code})</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">方向</span>
                <span className={`font-medium ${direction === "buy" ? "text-red-500" : "text-green-500"}`}>
                  {direction === "buy" ? "买入" : "卖出"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">价格</span>
                <span className="font-medium">{parseFloat(price).toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">数量</span>
                <span className="font-medium">{quantity} 股</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">金额</span>
                <span className="font-bold">{(parseFloat(price) * parseInt(quantity)).toFixed(2)}</span>
              </div>
            </div>
            {note && (
              <div className="text-sm text-gray-500">
                备注: {note}
              </div>
            )}
            <div className="flex gap-3">
              <button onClick={() => setConfirm(false)} className="flex-1 py-3 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
                返回修改
              </button>
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="flex-1 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
              >
                {loading ? "提交中..." : "确认下单"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
