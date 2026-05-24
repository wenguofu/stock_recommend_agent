/**
 * 板块 → ETF 映射常量
 * 集中管理，组件只 import 使用
 */
export const SECTOR_ETFS: Record<string, { code: string; name: string }[]> = {
  '消费电子': [{ code: '159732', name: '消费电子ETF' }],
  '半导体': [{ code: '159995', name: '芯片ETF' }, { code: '512760', name: '半导体ETF' }],
  '人工智能': [{ code: '515070', name: 'AIETF' }, { code: '159930', name: '人工智能ETF' }],
  '新能源车': [{ code: '515030', name: '新能源车ETF' }, { code: '159637', name: '新能源汽车ETF' }],
  '光伏': [{ code: '159857', name: '光伏ETF' }, { code: '516880', name: '光伏50ETF' }],
  '医药生物': [{ code: '159929', name: '医药ETF' }, { code: '512010', name: '医药卫生ETF' }],
  '机器人': [{ code: '159770', name: '机器人ETF' }, { code: '159712', name: '机器人ETF' }],
  '证券': [{ code: '512880', name: '证券ETF' }, { code: '510230', name: '金融ETF' }],
  '军工': [{ code: '512660', name: '军工ETF' }, { code: '159959', name: '军工ETF' }],
  '白酒': [{ code: '161725', name: '白酒基金' }, { code: '159928', name: '消费ETF' }],
  '通信/5G': [{ code: '515050', name: '5GETF' }, { code: '515880', name: '通信ETF' }],
  '电力/能源': [{ code: '159611', name: '电力ETF' }, { code: '516910', name: '能源ETF' }],
  '算力/数据中心': [{ code: '159738', name: '云计算ETF' }, { code: '516510', name: '算力ETF' }],
  '半导体/芯片': [{ code: '159995', name: '芯片ETF' }],
  '人工智能AI': [{ code: '515070', name: 'AIETF' }],
  '白酒/消费': [{ code: '161725', name: '白酒基金' }, { code: '159928', name: '消费ETF' }],
  '证券/金融': [{ code: '512880', name: '证券ETF' }],
};

/** 智能匹配ETF（模糊搜索） */
export function findEtfs(sectorName: string): { code: string; name: string }[] | undefined {
  if (SECTOR_ETFS[sectorName]) return SECTOR_ETFS[sectorName];
  for (const [key, etfs] of Object.entries(SECTOR_ETFS)) {
    if (sectorName.includes(key) || key.includes(sectorName)) return etfs;
  }
  return undefined;
}
