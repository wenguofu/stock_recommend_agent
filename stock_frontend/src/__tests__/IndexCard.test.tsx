import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import IndexCard from '../components/IndexCard';

describe('IndexCard', () => {
  it('loading 时显示 Skeleton', () => {
    render(<IndexCard title="上证指数" data={undefined} isLoading={true} color="#1677ff" />);
    expect(screen.getByText('上证指数')).toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeTruthy();
  });

  it('无数据时显示 --', () => {
    render(<IndexCard title="深证成指" data={undefined} isLoading={false} color="#722ed1" />);
    expect(screen.getByText('深证成指')).toBeInTheDocument();
    expect(screen.getByText('--')).toBeInTheDocument();
  });

  it('涨幅为正显示红色', () => {
    render(
      <IndexCard
        title="创业板指"
        data={{ current_price: 3500.50, change_percent: 2.35, high: 3520.00, low: 3480.00, volume: 150000, yesterday_close: 3420.00 }}
        isLoading={false}
        color="#eb2f96"
      />
    );
    expect(screen.getByText('3500.50')).toBeInTheDocument();
    expect(screen.getByText('+2.35%')).toBeInTheDocument();
  });

  it('涨幅为负显示绿色', () => {
    render(
      <IndexCard
        title="道琼斯"
        data={{ current_price: 38000.00, change_percent: -1.50, high: 38500.00, low: 37900.00, volume: 200000, yesterday_close: 38580.00 }}
        isLoading={false}
        color="#1677ff"
      />
    );
    expect(screen.getByText('38000.00')).toBeInTheDocument();
    expect(screen.getByText('-1.50%')).toBeInTheDocument();
  });
});
