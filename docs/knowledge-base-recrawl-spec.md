# XBots Agent 知识库重爬与验收规范

## 1. 当前知识库审计结论

审计对象为 MySQL 中 `user_id = 0x00000000000000000000000000000000` 的系统公共知识库。本次仅做只读检查，没有修改数据库。

### 1.1 数据规模

| 指标 | 当前值 |
| --- | ---: |
| 文档数 | 6,155 |
| 分块数 | 27,260 |
| 平均每篇分块数 | 4.43 |
| 分块平均长度 | 437 字符 |
| 恰好 500 字符的分块 | 20,503（75.21%） |
| 小于 50 字符的分块 | 602 |
| 相邻分块采用 50 字符重叠 | 20,500 对 |

当前数据并非没有切分，而是由旧流程按约 500 字符、50 字符重叠机械切分。项目当前代码使用 900 字符、140 字符重叠，两者不一致。

### 1.2 主要问题

#### P0：来源与可追溯性

- 6,155 篇文档全部来自菜鸟教程，`source_type` 全部是 `system_course`，没有来源多样性。
- 6,155 篇文档的 `doc_metadata` 都没有结构化 `source_url`、`crawled_at`、`language`、`description`、版本号或发布日期。
- 原文 URL 被写进正文末尾模板，而不是元数据。引用链接只能依赖正文解析或根据 `doc_id` 猜测。
- 缺少版本和更新时间，PHP 4、Python 2 等历史内容与当前内容可能混合进入检索结果。

#### P0：正文抓取不完整

- 1,565 篇文档残留 `[mycode...]` 等站点短代码，说明大量代码示例没有被正确解析。
- 236 篇文档提到“如下图、流程图、如图”等图片内容，但全库只有 4 篇包含 Markdown 图片引用，图示语义基本丢失。
- 395 篇文档仍有 HTML 标签，1,078 篇仍有 HTML 实体。
- 每篇文档都包含抓取声明和“仅供个人学习使用”页尾模板，该模板还产生了大量极短、重复分块。

#### P1：分块破坏结构

- 75.21% 的分块长度恰好为 500 字符，证明旧流程主要按字符硬切。
- 6,286 个分块只含单边 Markdown 代码围栏；完整文档合并后仅 3 篇围栏仍不闭合，说明绝大部分是分块切断代码块造成的。
- 692 个分块从 Markdown 表格行中间开始。
- 14,019 个分块以中英文或数字直接结束，很多句子、标识符和代码被截断。
- 602 个极短分块会浪费向量条目，并放大页尾模板等无意义内容的召回概率。

#### P1：正文重复与噪声

- 所有首块都重复写入页面标题，6,149 篇首块还写入一段引用式摘要，5,735 篇随后再次出现 `intro`，摘要和正文经常重复。
- 有 194 个完全重复的额外分块、211 个归一化后重复的额外分块，多数是页尾模板碎片。
- 有 27 个重复标题；部分可能是不同 API 重载或不同章节，但当前元数据不足以区分。
- 正文包含 13,978 个不换行空格、24 个零宽字符和 7 个退格控制字符。
- 没有发现 Unicode `U+FFFD` 替换字符，因此主要不是字符集解码乱码，而是清洗和结构解析不完整。

#### P1：检索层附带问题

- 当前页面把 Chroma 相似度、RRF 排名融合分、网页检索分和目录规则分统一展示成百分比，它们并不是同一量纲。
- 关键词降级检索的三路 RRF 理论最高分约为 `3 / 61 = 0.04918`，但 Multi-Agent 流程还会过滤低于 `0.2` 的结果，可能误删全部关键词结果。
- 数据重爬可以改善内容质量，但不能单独修复上述评分归一化与阈值问题。

## 2. 最终交付目录

爬虫 Agent 必须交付一个完整目录，不得只交付单个无说明 JSON 文件。

```text
xbots-kb-v2/
├── README.md
├── manifest.json
├── checksums.sha256
├── documents/
│   ├── documents-00001.jsonl
│   └── ...
├── chunks/
│   ├── chunks-00001.jsonl
│   └── ...
├── tests/
│   └── golden_queries.jsonl
├── scripts/
│   ├── validate_dataset.py
│   └── run_retrieval_regression.py
└── reports/
    ├── crawl_failures.jsonl
    ├── validation_report.json
    ├── retrieval_report.json
    └── source_coverage.json
```

所有文本文件必须满足：

- UTF-8 编码且不带 BOM。
- 使用 LF 换行。
- JSONL 每行一个完整 JSON 对象，不使用跨行 JSON 对象。
- 每个分片文件最多 1,000 条记录，按稳定 ID 排序。
- JSON 序列化必须可重复；同一输入再次执行应得到相同内容哈希。
- 不交付 embedding。向量必须由 XBots 使用最终选定的 embedding 模型生成，避免模型和维度不兼容。

## 3. 文档文件格式

`documents/*.jsonl` 每行代表一篇清洗后的完整原文：

```json
{
  "schema_version": "2.0",
  "document_id": "sha256:稳定ID",
  "canonical_url": "https://docs.example.com/topic/page",
  "source_domain": "docs.example.com",
  "source_name": "Example 官方文档",
  "source_type": "official_documentation",
  "title": "准确且不含站点后缀的标题",
  "description": "不超过 300 字且不与正文机械重复的摘要",
  "language": "zh-CN",
  "category": "python",
  "tags": ["sorting", "algorithm"],
  "content_markdown": "# 标题\n\n清洗后的完整 Markdown 正文",
  "headings": [
    {"level": 1, "text": "标题", "anchor": "title"}
  ],
  "published_at": null,
  "updated_at": "2026-07-01T00:00:00Z",
  "crawled_at": "2026-07-15T12:00:00Z",
  "content_version": "页面或软件版本；未知则为 null",
  "license": "许可证或版权说明；无法确认则为 null",
  "http_status": 200,
  "content_sha256": "仅对规范化 content_markdown 计算的 sha256"
}
```

字段约束：

- `document_id` 必须稳定，建议由规范化 `canonical_url` 计算，不得使用数据库自增 ID。
- `canonical_url` 必须是最终跳转后的绝对 URL，去除追踪参数，保留有语义的路径和查询参数。
- `source_type` 只能使用约定枚举，例如 `official_documentation`、`standard`、`academic`、`maintainer_blog`、`tutorial`。
- `category` 使用统一小写 slug，不把站点栏目名直接当分类。
- `title` 不包含“| 菜鸟教程”等站点后缀，不允许 `N/A`、空字符串或纯序号。
- `content_markdown` 是可独立阅读的正文，不包含导航、广告、Cookie 提示、相关推荐、版权页尾或抓取声明。
- 未知值使用 `null`，不得捏造作者、时间、版本、摘要或许可证。

## 4. 分块文件格式

`chunks/*.jsonl` 每行代表一个可直接导入检索系统的语义片段：

```json
{
  "schema_version": "2.0",
  "chunk_id": "sha256:document-id#0001",
  "document_id": "sha256:稳定ID",
  "chunk_index": 0,
  "title": "文档标题",
  "heading_path": ["快速排序", "分区过程"],
  "content": "一个语义完整、无需依赖前后截断文本即可理解的片段",
  "language": "zh-CN",
  "category": "algorithms",
  "tags": ["quick-sort", "divide-and-conquer"],
  "source_url": "https://docs.example.com/quick-sort#partition",
  "source_domain": "docs.example.com",
  "source_type": "official_documentation",
  "char_count": 428,
  "token_count": 312,
  "content_sha256": "片段正文 sha256"
}
```

分块规则：

1. 使用 Markdown AST 或 DOM 结构切分，优先按 H1/H2/H3、段落和列表边界切分，不按固定字符数直接截断。
2. 目标长度为 300 至 700 tokens，硬上限 900 tokens；小于 120 tokens 的片段应与相邻同主题内容合并，独立定义、公式或短代码除外。
3. 代码块、Markdown 表格、公式、步骤列表必须保持原子性。超过硬上限时按其内部合法边界拆分，并在 `heading_path` 中保留上下文。
4. 不得在句子、URL、标识符、Markdown 链接、代码字符串或表格行中间截断。
5. 仅对连续长 prose 使用 40 至 80 tokens 的重叠。标题、表格、代码和模板文本不得机械重复。
6. 标题和标题路径放入独立字段，不在每个片段正文中反复堆叠。生成 embedding 输入时再组合 `title + heading_path + content`。
7. 每个片段必须带可打开的 `source_url`；有锚点时直接定位到对应章节。
8. 文档级去重后再分块，分块后再次做精确去重和近似去重。

## 5. 抓取与清洗要求

### 5.1 来源策略

- 优先级：官方文档/标准规范 > 项目维护者文档 > 高质量教程 > 社区内容。
- 每个技术主题尽量覆盖至少两个独立可信域名，避免单一站点垄断检索结果。
- 对版本敏感内容必须记录版本。默认收录当前稳定版本；历史版本必须明确标注，不与当前版本混在同一分类。
- 遵守 robots.txt、网站服务条款、许可证和限速要求。禁止绕过登录、验证码、付费墙或反爬限制。
- 不要为了数量抓取低信息页面、纯索引页、标签页、搜索结果页和重复镜像。

### 5.2 正文清洗

- 正确检测响应编码，统一为 Unicode NFC。
- 将 NBSP 转为空格，删除零宽字符和非法控制字符，但不得破坏代码缩进和换行。
- 将 HTML 实体解码，将正文 HTML 转为规范 Markdown。
- 删除导航、页眉页脚、广告、版权模板、推荐列表、分享按钮和抓取器声明。
- 将站点专用代码短标签解析为完整 fenced code block；无法恢复代码时将页面写入失败记录，不得保留 `[mycode]` 占位符冒充正文。
- 保留代码语言、表格、公式、列表层级、提示框语义、图片说明和链接。
- 相对链接转换为绝对 canonical URL。
- 图片影响理解时，保留图片 URL、alt 和 caption；不得根据图片文件名臆造图中内容。需要 OCR 时记录 OCR 来源和置信度。
- 不生成“以上代码”“如下图”却缺少对应代码或图片的孤立文本。
- 不把自动摘要重复写入正文；摘要只能放在 `description`。

### 5.3 去重

- URL 规范化后去除同页参数变体。
- 使用 `content_sha256` 做精确去重。
- 使用 MinHash/SimHash 或 embedding 做近似去重；正文相似度超过 0.95 时只保留质量和时效性更好的版本，并记录被合并 URL。
- 同标题但正文不同的 API 重载不能简单删除，必须通过版本、签名、分类或 canonical URL 区分。

## 6. 回归测试与硬性验收门槛

爬虫 Agent 必须实际运行测试并提交报告，不能只声称“已测试”。任一硬性项失败都不得标记交付完成。

### 6.1 Schema 与文件完整性

1. 校验所有 JSON/JSONL 均可解析。
2. 按 schema 校验每个字段类型、枚举、时间格式和必填字段。
3. 校验 `manifest.json` 记录数与实际行数一致。
4. 校验 `checksums.sha256` 覆盖所有交付文件且全部匹配。
5. 校验 `document_id`、`chunk_id` 全局唯一且重复运行保持稳定。

硬性门槛：解析成功率、schema 通过率、ID 唯一率和校验和通过率均为 100%。

### 6.2 清洗质量

1. 扫描 `U+FFFD`、BOM、零宽字符、非法控制字符和未解码 HTML 实体。
2. 扫描原始 HTML、站点短代码、导航词、广告词和页尾模板。
3. 验证 Markdown 可解析、代码围栏成对、表格列数基本一致、链接语法完整。
4. 检测“如下图/以上代码”是否存在对应图片、caption 或代码块。
5. 人工随机抽查至少 100 篇文档，覆盖所有主要分类和来源域名。

硬性门槛：乱码替换符、非法控制字符、原始短代码、模板页尾和不闭合代码围栏均为 0；人工抽查严重缺失为 0。

### 6.3 分块质量

1. 校验片段不在句子、代码块、表格行、公式或 Markdown 链接中间截断。
2. 校验 token 长度分布并列出 P50、P90、P95、P99。
3. 校验小于 120 tokens 和大于 900 tokens 的例外均有明确原因。
4. 校验每篇文档 `chunk_index` 从 0 连续递增。
5. 校验片段可以按顺序还原文档核心正文，不能丢失章节。

硬性门槛：无理由越界片段为 0；顺序错误为 0；结构中间截断为 0。

### 6.4 去重与来源质量

1. 校验精确重复文档和精确重复分块。
2. 对近似重复候选人工抽查至少 100 对。
3. 统计来源域名、分类、语言、版本和时间覆盖率。
4. 检查单一域名占比并说明原因。
5. 对全部 URL 做格式校验，对抽样 URL 做 HTTP 可访问性和锚点校验。

硬性门槛：精确重复为 0；近似重复率低于 1%；必填 URL 覆盖率 100%；抽样可访问率不低于 98%。

### 6.5 离线检索回归

`tests/golden_queries.jsonl` 至少包含 100 条人工标注查询，覆盖：

- 概念解释。
- 精确 API/命令查询。
- 代码问题。
- 中文、英文和中英混合查询。
- 同义词和口语表达。
- 版本敏感问题。
- 模糊查询。
- 当前知识库范围外的问题。
- 不应触发课程资料检索的实时问题，例如天气、新闻、价格。

每行格式：

```json
{
  "query_id": "q-0001",
  "query": "Python 快速排序如何实现",
  "expected_document_ids": ["sha256:..."],
  "expected_categories": ["python", "algorithms"],
  "forbidden_document_ids": [],
  "should_retrieve": true,
  "notes": "应优先返回包含完整代码和复杂度说明的页面"
}
```

对 BM25、向量检索和混合检索分别运行，并报告 Recall@5、MRR@5、nDCG@10、无关结果率和来源多样性。

建议验收门槛：混合检索 Recall@5 不低于 0.85，MRR@5 不低于 0.75，nDCG@10 不低于 0.80；范围外查询的误检率不高于 5%。如果未达到，必须分析失败查询并重新清洗、分块或调整标注，不能只提高 top_k 掩盖问题。

### 6.6 XBots 端到端回归

1. 使用临时数据库或独立 collection 导入，禁止直接覆盖正式公共库。
2. 验证导入文档数、分块数、metadata 和内容哈希完全一致。
3. 使用项目最终 embedding 模型生成 Chroma 向量，验证向量条目数等于有效分块数。
4. 运行 golden queries，检查 Top 5 标题、正文和来源链接。
5. 点击每条参考来源，确认能打开原文章节，而不是跳转到站点首页或猜测 URL。
6. 测试概念、代码、学习规划、实时信息、闲聊等不同类型问题，确认不相关知识库不会被强行引用。
7. 测试同一查询重复执行的结果稳定性以及多用户只读公共库权限。
8. 记录导入耗时、索引耗时、查询 P50/P95、内存和磁盘占用；不得出现超时、空索引或请求阻塞。
9. 验证失败时可删除临时 collection 并恢复旧库，正式切换前必须保留旧库备份。

## 7. 可直接交给爬虫 Agent 的提示词

如果爬虫 Agent 不在本项目目录、无法读取本文件，请改用独立任务书：

`docs/crawler-agent-standalone-prompt.md`

下面的提示词适用于能够同时读取本规范的 Agent。

```text
你负责为 XBots Agent 重新构建一套生产可用的公共学习知识库。不要修改 XBots 的正式数据库，不要覆盖旧知识库，也不要只交付一个未经验证的 JSON 文件。你的最终产物必须是可审计、可重复导入、可回归测试的数据包。

目标：
1. 获取高质量、可追溯、适合 RAG 的技术学习资料。
2. 优先使用官方文档、标准规范和项目维护者资料，再补充高质量教程。
3. 避免来源全部集中在菜鸟教程；每个主要技术主题尽量覆盖至少两个独立可信域名。
4. 严格遵守 robots.txt、服务条款、版权和访问频率限制，不绕过登录、验证码、付费墙或反爬机制。
5. 对版本敏感内容记录明确版本和更新时间，不把历史版本与当前稳定版本混为一谈。

你必须先阅读并严格执行《XBots Agent 知识库重爬与验收规范》。按规范完成以下工作：

A. 制定抓取计划
- 输出来源 allowlist、主题分类、预计页面数、版本范围、限速和失败重试策略。
- 排除导航页、标签页、搜索结果页、广告页、重复镜像和低信息页面。
- canonical URL 必须稳定，去掉跟踪参数并处理重定向。

B. 抓取与清洗
- 正确处理编码，统一 Unicode NFC、UTF-8 无 BOM、LF 换行。
- 提取完整正文、代码、表格、公式、列表、标题层级、图片 caption 和原文链接。
- 将 HTML 转为规范 Markdown，删除导航、广告、推荐、分享、Cookie、页眉页脚和抓取声明。
- 解析站点专用代码短标签。无法恢复代码、表格或关键图片时，将页面写入 crawl_failures.jsonl，不得用占位符冒充完整正文。
- 不捏造作者、时间、版本、摘要、图片内容或许可证；未知值写 null。

C. 去重与语义分块
- 先按 canonical URL、内容哈希和近似相似度做文档去重。
- 使用 Markdown AST/DOM 按标题、段落和语义边界分块。
- 目标 300-700 tokens，硬上限 900 tokens；小于 120 tokens 时原则上合并。
- 代码块、表格、公式和步骤列表保持完整，不得在句子、URL、标识符、链接或表格行中间截断。
- 只在长 prose 中使用 40-80 tokens 重叠，不机械重复标题和模板。
- 每个分块必须携带 document_id、heading_path、source_url、category、language、version 和内容哈希。
- 不生成 embedding，XBots 会使用最终 embedding 模型统一建库。

D. 交付文件
- 严格按规范生成 README.md、manifest.json、checksums.sha256、documents/*.jsonl、chunks/*.jsonl、tests/golden_queries.jsonl、scripts/validate_dataset.py、scripts/run_retrieval_regression.py 和 reports 下的全部报告。
- JSONL 每行一个对象，每个分片最多 1,000 条，按稳定 ID 排序。
- manifest 中记录 schema 版本、生成时间、抓取器版本、来源统计、文档数、分块数、失败数、去重数、分类统计和分块策略。

E. 测试与验收
- 实际运行 schema、编码、清洗、Markdown、分块边界、去重、URL、哈希和人工抽样测试。
- 至少制作 100 条人工标注 golden queries，覆盖概念、API、代码、中英混合、同义词、版本、模糊查询、范围外问题以及天气/新闻等不应检索课程资料的问题。
- 分别测试 BM25、向量和混合检索，输出 Recall@5、MRR@5、nDCG@10、误检率和失败案例。
- 在临时数据库/临时 Chroma collection 中执行一次完整导入和查询回归，禁止直接覆盖正式库。
- 验证参考来源可以直接打开对应原文章节。
- 所有硬性验收项通过后才能声明完成。若有失败，修复后重新运行完整测试，并在报告中保留失败原因和修复记录。

最终回复必须包含：
1. 交付目录的绝对路径。
2. 文档数、分块数、来源域名数、失败数和去重数。
3. 所有硬性测试的通过/失败汇总。
4. Recall@5、MRR@5、nDCG@10 和范围外误检率。
5. 尚未解决的风险，不得隐瞒或用“基本可用”代替具体结果。
6. 明确声明未修改正式数据库、未删除旧知识库。
```

## 8. 正式替换前的项目侧工作

新数据包通过验收后，XBots 侧还应单独完成：

1. 编写 v2 导入器，按 manifest 和 checksum 校验后事务性导入。
2. 为 `KnowledgeDocument` 和 `KnowledgeChunk` 补齐 `canonical_url`、`source_domain`、`language`、版本、时间和内容哈希等可查询字段，或确保 JSON metadata 有对应索引策略。
3. 使用新 collection 名称重建 Chroma，完成回归后再原子切换。
4. 统一 Chroma、RRF、网页搜索和规则检索的 `score_type`，只对已校准分数展示百分比。
5. 修复 RRF 最高约 0.049 却使用 0.2 固定阈值的问题。
6. 保留旧库快照和一键回滚方案，观察真实查询一段时间后再清理旧数据。
