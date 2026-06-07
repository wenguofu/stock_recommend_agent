/**
 * Sprint5: 告警中心 UI
 *
 * - 查看已配置的告警通道
 * - 发送测试告警
 * - 查看缓存状态
 */
import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Card, Form, Input, Select, Button, Space, Row, Col, Tag, Alert,
  Statistic, Typography, Divider, App,
} from 'antd';
import { stockAPI } from '../services/api';

const { Text } = Typography;

export default function AlertCenter() {
  const { message } = App.useApp();
  const [level, setLevel] = useState<'info' | 'warn' | 'error'>('warn');
  const [title, setTitle] = useState('测试告警');
  const [content, setContent] = useState('这是来自股票交易系统的测试告警');

  const channels = useQuery({
    queryKey: ['alert-channels'],
    queryFn: () => stockAPI.getAlertChannels(),
  });

  const cacheStats = useQuery({
    queryKey: ['cache-stats'],
    queryFn: () => stockAPI.getCacheStats(),
    refetchInterval: 5000,
  });

  const sendMut = useMutation({
    mutationFn: () => stockAPI.sendAlert(level, title, content),
    onSuccess: (r) => {
      if (r.sent) {
        message.success(`已发送 (channels: ${Object.keys(r.channels || {}).join(', ')})`);
      } else {
        message.warning('未发送: ' + (r.reason || 'unknown'));
      }
    },
  });

  const clearCacheMut = useMutation({
    mutationFn: () => stockAPI.clearCache(),
    onSuccess: () => {
      message.success('缓存已清空');
      cacheStats.refetch();
    },
  });

  const cfg = channels.data?.configured || {};

  return (
    <div style={{ padding: 16 }}>
      <h2>告警 & 缓存中心</h2>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="告警通道状态">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Tag color={cfg.feishu ? 'green' : 'default'}>
                  飞书机器人: {cfg.feishu ? '已配置' : '未配置 (设置 FEISHU_WEBHOOK_URL)'}
                </Tag>
              </div>
              <div>
                <Tag color={cfg.dingtalk ? 'green' : 'default'}>
                  钉钉机器人: {cfg.dingtalk ? (cfg.dingtalk_signed ? '已配置+加签' : '已配置') : '未配置'}
                </Tag>
              </div>
              <div>
                <Tag color={cfg.generic ? 'green' : 'default'}>
                  通用 Webhook: {cfg.generic ? '已配置' : '未配置 (设置 GENERIC_WEBHOOK_URL)'}
                </Tag>
              </div>
              <Divider />
              <Text type="secondary">
                级别过滤: {channels.data?.level_filter} (低于此级别的告警不会发送)
              </Text>
            </Space>
          </Card>

          <Card title="发送测试告警" style={{ marginTop: 16 }}>
            <Form layout="vertical">
              <Form.Item label="级别">
                <Select
                  value={level}
                  onChange={setLevel}
                  options={[
                    { value: 'info', label: 'Info (信息)' },
                    { value: 'warn', label: 'Warn (警告)' },
                    { value: 'error', label: 'Error (严重)' },
                  ]}
                />
              </Form.Item>
              <Form.Item label="标题">
                <Input value={title} onChange={e => setTitle(e.target.value)} />
              </Form.Item>
              <Form.Item label="内容">
                <Input.TextArea
                  value={content}
                  onChange={e => setContent(e.target.value)}
                  rows={3}
                />
              </Form.Item>
              <Button
                type="primary"
                loading={sendMut.isPending}
                onClick={() => sendMut.mutate()}
              >
                发送
              </Button>
            </Form>
          </Card>
        </Col>

        <Col span={12}>
          <Card title="缓存状态">
            {cacheStats.data && (
              <Row gutter={16}>
                <Col span={12}>
                  <Statistic
                    title="后端"
                    value={cacheStats.data.backend || 'memory'}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="命中率"
                    value={(cacheStats.data.hit_rate != null
                      ? (cacheStats.data.hit_rate * 100).toFixed(1) + '%'
                      : 'N/A')}
                  />
                </Col>
                <Col span={12}>
                  <Statistic title="命中次数" value={cacheStats.data.hits || 0} />
                </Col>
                <Col span={12}>
                  <Statistic title="未命中" value={cacheStats.data.misses || 0} />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="大小"
                    value={cacheStats.data.size != null ? cacheStats.data.size : 'N/A'}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="容量"
                    value={cacheStats.data.max_size != null ? cacheStats.data.max_size : 'N/A'}
                  />
                </Col>
              </Row>
            )}
            <Divider />
            <Button
              danger
              loading={clearCacheMut.isPending}
              onClick={() => clearCacheMut.mutate()}
            >
              清空缓存
            </Button>
            <Alert
              style={{ marginTop: 12 }}
              type="info"
              showIcon
              message="缓存作用"
              description={
                <ul>
                  <li>Redis 优先, REDIS_URL 环境变量配置</li>
                  <li>无 Redis 时自动降级到内存 LRU (容量 1024)</li>
                  <li>可缓存 K 线 / 因子值 / 任何 JSON 可序列化的对象</li>
                </ul>
              }
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
