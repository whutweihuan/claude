# MyFarm 状态

- 阶段: 测试基建完成（puppeteer-core + 系统 Chrome + 本地 three vendor），开始写游戏
- 交付: myfarm/index.html 单文件；Three.js r160 走 jsDelivr CDN（需联网，UI 有提示）
- 验收: `cd myfarm/test && node run.js` 全 PASS（启动/购买/种植/生长/收获/售卖/天气/昼夜/设置/暂停/续档/无 JS 错误 + 人工检查 shots/*.png）
- 下一步: index.html 分 3 块写 → chunk1 骨架/CSS/音频 → chunk2 世界与作物 → chunk3 经营逻辑/UI/主循环
- 验证命令: `cd D:/000_study/020_code/claude/myfarm/test && node run.js`
- 关键数值: 起始金币100；白菜 种5/售14/25s；12种作物；天气 晴1.0/阴0.8/雨1.2/雹0.5；白天180s
- 已知问题: （空）
