import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ErrorBoundary from '../components/ErrorBoundary';

vi.spyOn(console, 'error').mockImplementation(() => {});

function ThrowError({ message }: { message: string }) {
  throw new Error(message);
  return null;
}

describe('ErrorBoundary', () => {
  it('正常渲染子组件', () => {
    render(
      <ErrorBoundary>
        <div>正常内容</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('正常内容')).toBeInTheDocument();
  });

  it('捕获错误并显示错误页面', () => {
    render(
      <ErrorBoundary>
        <ThrowError message="测试错误" />
      </ErrorBoundary>
    );
    expect(screen.getByText('页面出现错误')).toBeInTheDocument();
    expect(screen.getByText('测试错误')).toBeInTheDocument();
  });

  it('显示重试和刷新按钮', () => {
    render(
      <ErrorBoundary>
        <ThrowError message="崩溃了" />
      </ErrorBoundary>
    );
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /刷新页面/ })).toBeInTheDocument();
  });
});
