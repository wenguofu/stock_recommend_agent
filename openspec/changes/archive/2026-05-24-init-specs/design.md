## Why

本项目是一个功能丰富但缺乏规格文档的 A 股量化交易系统。需要通过 OpenSpec 规范化：
1. 为所有现有模块建立规格文档
2. 记录 API 契约
3. 识别待优化点
4. 建立测试基准

## What Changes

- 新增 `openspec/specs/` 下 8 个模块 spec 文档
- 文档化所有 API 端点的输入输出契约
- 记录已知技术债和优化方向

## Impact

- 纯文档变更，不影响运行代码
- 为后续 `openspec change` 优化提案提供基准
