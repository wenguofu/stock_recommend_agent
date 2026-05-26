import type { ThemeConfig } from 'antd';
import { theme } from 'antd';

const sharedToken = {
  borderRadius: 6,
  fontFamily: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif`,
};

export const lightTheme: ThemeConfig = {
  cssVar: { prefix: 'ant' },
  token: {
    colorPrimary: '#1677ff',
    ...sharedToken,
  },
};

export const darkTheme: ThemeConfig = {
  cssVar: { prefix: 'ant' },
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#1677ff',
    ...sharedToken,
  },
};
