/**
 * 设计 Token 中心 — 修复 Sprint3: 前端硬编码颜色/字号散落
 *
 * A 股颜色约定 (中国市场):
 *   红涨 = 上涨
 *   绿跌 = 下跌
 * 与国际市场 (绿涨/红跌) 相反, 此处锁定 A 股语义。
 *
 * 使用方式:
 *   import { stockUpColor, stockDownColor, fontSizeMd } from '@/constants/tokens';
 */

// ─── 涨跌色 (A 股市场约定) ───
export const stockUpColor = '#cf1322';      // 涨(中国红)
export const stockDownColor = '#3f8600';    // 跌(中国绿)
export const stockUpSoft = '#fff1f0';       // 涨浅背景
export const stockDownSoft = '#f6ffed';     // 跌浅背景
export const stockFlatColor = '#888888';    // 平盘

// ─── 语义色 (antd 5.x) ───
export const semanticSuccess = '#52c41a';   // 利好/正贡献
export const semanticWarning = '#faad14';   // 中性/警告
export const semanticError = '#ff4d4f';     // 利空/负贡献
export const semanticInfo = '#1677ff';      // 信息/中性

// ─── 图表色 (K 线专用) ───
export const chartUpColor = '#ef5350';      // K线 涨
export const chartDownColor = '#26a69a';    // K线 跌

// ─── 字号 token ───
export const fontSizeXs = 12;
export const fontSizeSm = 13;
export const fontSizeBase = 14;
export const fontSizeMd = 16;
export const fontSizeLg = 18;
export const fontSizeXl = 22;
export const fontSizeXxl = 28;

// ─── 间距 token ───
export const spaceXs = 4;
export const spaceSm = 8;
export const spaceMd = 16;
export const spaceLg = 24;
export const spaceXl = 32;

// ─── 工具函数: 涨跌色 ───
export function upDownColor(value: number | null | undefined): string {
  if (value == null) return stockFlatColor;
  if (value > 0) return stockUpColor;
  if (value < 0) return stockDownColor;
  return stockFlatColor;
}

export function semanticColor(value: number, threshold = 0): string {
  if (value > threshold) return semanticSuccess;
  if (value < threshold) return semanticError;
  return semanticWarning;
}
