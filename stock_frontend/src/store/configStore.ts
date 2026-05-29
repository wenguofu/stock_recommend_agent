/**
 * 配置状态管理
 * 非敏感配置 (URL/Provider) → localStorage 持久化
 * API密钥 → sessionStorage (关闭标签页后清除)
 */
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

const DEFAULT_API_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';

interface ConfigState {
  apiBaseURL: string;
  openaiApiKey: string;
  deepseekApiKey: string;
  qwenApiKey: string;
  geminiApiKey: string;
  grokApiKey: string;
  defaultAiProvider: string;
  setApiBaseURL: (url: string) => void;
  setOpenaiApiKey: (key: string) => void;
  setDeepseekApiKey: (key: string) => void;
  setQwenApiKey: (key: string) => void;
  setGeminiApiKey: (key: string) => void;
  setGrokApiKey: (key: string) => void;
  setDefaultAiProvider: (provider: string) => void;
}

// localStorage — 只持久化非敏感配置
const nonSensitiveStore = create<ConfigState>()(
  persist(
    (set) => ({
      apiBaseURL: DEFAULT_API_URL,
      openaiApiKey: '',
      deepseekApiKey: '',
      qwenApiKey: '',
      geminiApiKey: '',
      grokApiKey: '',
      defaultAiProvider: 'openai',
      setApiBaseURL: (url) => set({ apiBaseURL: url }),
      setOpenaiApiKey: (key) => set({ openaiApiKey: key }),
      setDeepseekApiKey: (key) => set({ deepseekApiKey: key }),
      setQwenApiKey: (key) => set({ qwenApiKey: key }),
      setGeminiApiKey: (key) => set({ geminiApiKey: key }),
      setGrokApiKey: (key) => set({ grokApiKey: key }),
      setDefaultAiProvider: (provider) => set({ defaultAiProvider: provider }),
    }),
    {
      name: 'stock-config',
      // 只持久化非敏感字段，密钥仅保存在 sessionStorage
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        openaiApiKey: state.openaiApiKey,
        deepseekApiKey: state.deepseekApiKey,
        qwenApiKey: state.qwenApiKey,
        geminiApiKey: state.geminiApiKey,
        grokApiKey: state.grokApiKey,
        defaultAiProvider: state.defaultAiProvider,
      }),
    }
  )
);

export const useConfigStore = nonSensitiveStore;

// 同步 baseURL 到 localStorage（独立于 sessionStorage 的密钥）
const savedUrl = localStorage.getItem('stock-base-url');
if (savedUrl) {
  try {
    const store = useConfigStore.getState();
    if (store.apiBaseURL === DEFAULT_API_URL) {
      store.setApiBaseURL(savedUrl);
    }
  } catch { /* ignore */ }
}

// 订阅 baseURL 变化并持久化到 localStorage
useConfigStore.subscribe((state) => {
  localStorage.setItem('stock-base-url', state.apiBaseURL);
});
