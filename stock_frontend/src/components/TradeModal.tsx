import { useState } from "react";
import { Modal, Form, Input, InputNumber, Button, Alert, Space, Typography, Select, Spin } from "antd";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface TradeModalProps {
  accountId: number;
  onClose: () => void;
  onSuccess: () => void;
}

export default function TradeModal({ accountId, onClose, onSuccess }: TradeModalProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [isEtfReplaced, setIsEtfReplaced] = useState(false);
  const [stockName, setStockName] = useState("");
  const [stockPrice, setStockPrice] = useState<number | undefined>(undefined);

  const handleFetchStock = async () => {
    const code = form.getFieldValue('code')?.trim();
    if (!/^\d{6}$/.test(code)) {
      setError("请输入6位A股代码");
      return;
    }
    setFetching(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/sina/realtime/${code}`);
      if (!res.ok) throw new Error("获取股票信息失败");
      const data = await res.json();
      setStockName(data.name || "");
      setStockPrice(data.current_price);
      form.setFieldsValue({ name: data.name || "", price: data.current_price || 0 });
      setIsEtfReplaced(code.startsWith("688"));
    } catch (e) {
      setError("获取股票信息失败，请检查代码是否正确");
    } finally {
      setFetching(false);
    }
  };

  const handleSubmit = async () => {
    if (!confirm) {
      const values = form.getFieldsValue();
      if (!values.code || !values.price || !values.quantity) return;
      setConfirm(true);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const values = form.getFieldsValue();
      const res = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: values.code?.trim(),
          name: values.name || stockName,
          direction: values.direction,
          price: values.price,
          quantity: values.quantity,
          note: values.note,
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

  const formValues = Form.useWatch([], form);
  const totalAmount = formValues?.price && formValues?.quantity
    ? (formValues.price * formValues.quantity).toFixed(2)
    : "0.00";

  return (
    <Modal
      title={confirm ? "确认交易" : "手动交易"}
      open
      onCancel={onClose}
      footer={null}
      width={500}
      destroyOnClose
    >
      {error && (
        <Alert message={error} type="error" showIcon style={{ marginBottom: 16 }} />
      )}

      {isEtfReplaced && !confirm && (
        <Alert
          message="科创板代码(688开头)将自动替换为对应ETF进行模拟交易"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {!confirm ? (
        <Form form={form} layout="vertical" initialValues={{ direction: 'buy', quantity: 100 }}>
          <Form.Item label="股票代码" required>
            <Space.Compact style={{ width: '100%' }}>
              <Form.Item name="code" noStyle rules={[{ required: true, message: '请输入股票代码' }]}>
                <Input placeholder="6位A股代码" maxLength={6} style={{ width: '100%' }} />
              </Form.Item>
              <Button
                onClick={handleFetchStock}
                loading={fetching}
                disabled={fetching || (form.getFieldValue('code')?.length !== 6)}
              >
                查询
              </Button>
            </Space.Compact>
          </Form.Item>

          <Form.Item label="股票名称" name="name">
            <Input placeholder="自动填充或手动输入" />
          </Form.Item>

          <Form.Item label="方向" name="direction" required>
            <Select
              options={[
                { label: '买入', value: 'buy' },
                { label: '卖出', value: 'sell' },
              ]}
            />
          </Form.Item>

          <Form.Item label="价格" name="price" required rules={[{ required: true, message: '请输入价格' }]}>
            <InputNumber style={{ width: '100%' }} step={0.01} min={0} placeholder="0.00" />
          </Form.Item>

          <Form.Item label="数量（股）" name="quantity" required rules={[{ required: true, message: '请输入数量' }]}>
            <InputNumber style={{ width: '100%' }} min={100} step={100} placeholder="A股最小100股" />
          </Form.Item>

          <Form.Item label="备注（可选）" name="note">
            <Input.TextArea rows={2} />
          </Form.Item>

          <Button
            type="primary"
            block
            onClick={handleSubmit}
            disabled={!formValues?.code || !formValues?.price || !formValues?.quantity}
          >
            下一步 - 确认交易
          </Button>
        </Form>
      ) : (
        <Space direction="vertical" style={{ width: '100%' }}>
          <div style={{
            background: '#f5f5f5', padding: 16, borderRadius: 8,
          }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography.Text type="secondary">股票</Typography.Text>
                <Typography.Text strong>{formValues?.name || stockName} ({formValues?.code})</Typography.Text>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography.Text type="secondary">方向</Typography.Text>
                <Typography.Text strong style={{ color: formValues?.direction === 'buy' ? '#ff4d4f' : '#52c41a' }}>
                  {formValues?.direction === 'buy' ? '买入' : '卖出'}
                </Typography.Text>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography.Text type="secondary">价格</Typography.Text>
                <Typography.Text strong>{formValues?.price?.toFixed(2)}</Typography.Text>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography.Text type="secondary">数量</Typography.Text>
                <Typography.Text strong>{formValues?.quantity} 股</Typography.Text>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography.Text type="secondary">金额</Typography.Text>
                <Typography.Text strong>{totalAmount}</Typography.Text>
              </div>
            </Space>
          </div>
          {formValues?.note && (
            <Typography.Text type="secondary">备注: {formValues.note}</Typography.Text>
          )}
          <div style={{ display: 'flex', gap: 12 }}>
            <Button block onClick={() => setConfirm(false)}>返回修改</Button>
            <Button type="primary" block onClick={handleSubmit} loading={loading}>
              确认下单
            </Button>
          </div>
        </Space>
      )}
    </Modal>
  );
}
