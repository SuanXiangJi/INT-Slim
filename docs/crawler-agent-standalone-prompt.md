# 外部知识库爬取 Agent 独立任务书

以下内容可以完整发送给不在 XBots Agent 项目目录中的另一个 Agent。它不需要访问 XBots 源码、数据库或运行服务。

```text
你需要在你自己的独立工作空间中，为一个中文 AI 学习助手构建生产可用的技术知识库数据包。你无法访问目标项目的源码、MySQL、Chroma、API 或旧知识库，这是正常且必须遵守的边界。你只负责调研来源、合规抓取、正文清洗、去重、语义分块、数据校验和本地检索回归。完成后，我会把整个数据包转交给目标项目的开发 Agent 进行导入和项目侧测试。

不要要求目标项目目录，不要连接或修改任何正式数据库，不要生成项目专用迁移脚本，不要假设目标项目已经安装任何依赖。所有代码、缓存、原始材料和最终数据都放在你自己的工作目录中。

## 一、目标

构建一套适用于 RAG 和学习辅导的中文技术知识库，重点满足：

1. 内容完整、可独立阅读，代码、表格、公式、步骤和图片说明不缺失。
2. 每篇文档和每个语义片段都能追溯到可直接打开的原文章节。
3. 来源以官方文档、标准规范和项目维护者资料为主，高质量教程为辅。
4. 不依赖单一站点，不允许绝大多数内容都来自菜鸟教程或任何其他单一域名。
5. 当前稳定版本和历史版本必须明确区分。
6. 数据经过真实回归测试，而不是只完成抓取后声称可用。

建议覆盖的一级主题包括：

- 编程基础：Python、Java、C、C++、JavaScript/TypeScript、Go。
- 数据与后端：SQL、MySQL、Redis、Linux、Git、Docker、HTTP/API。
- 数据科学：NumPy、Pandas、机器学习基础、PyTorch。
- AI 工程：LLM 基础、RAG、向量检索、Agent、工具调用、工作流和安全边界。

先保证核心主题的质量和完整性，再扩充数量。不要为了页面数抓取低信息页面、纯索引页、标签页、搜索结果页、重复镜像或自动聚合页面。

## 二、合规与来源策略

1. 遵守 robots.txt、网站服务条款、许可证、版权要求和访问频率限制。
2. 禁止绕过登录、验证码、付费墙、访问控制或反爬措施。
3. 每个来源先形成 allowlist，记录域名、来源类型、主题范围、版本、许可证/使用限制、限速和选择理由。
4. 来源优先级：官方文档或标准 > 项目维护者文档 > 高质量教程 > 社区文章。
5. 每个主要主题尽量覆盖至少两个独立可信域名。某个域名占全部文档的比例原则上不得超过 35%；超过时必须在报告中给出合理解释。
6. 版本敏感资料必须填写 `content_version` 和 `updated_at`。无法确认时填 `null`，不得猜测。
7. canonical URL 必须使用最终跳转地址，删除 utm 等追踪参数，但保留有业务含义的查询参数和章节锚点。

## 三、抓取和正文清洗

1. 正确检测响应编码，统一输出 Unicode NFC、UTF-8 无 BOM、LF 换行。
2. 仅保留文章主体，删除导航、广告、推荐列表、分享按钮、Cookie 提示、页眉页脚、版权模板和抓取器声明。
3. 将正文 HTML 转成结构规范的 Markdown，保留 H1/H2/H3 层级、段落、列表、表格、代码块、公式、提示框、链接、图片 alt 和 caption。
4. HTML 实体必须解码；NBSP 转普通空格；删除零宽字符、BOM、退格等非法控制字符，但不能破坏代码缩进。
5. 站点自定义代码标签，例如 `[mycode]`，必须恢复为完整 fenced code block。无法恢复关键代码、表格、公式或图片时，将该页面写入失败记录，不得把占位符当作正文交付。
6. 将相对链接转换成绝对 URL。正文引用的内部章节链接应指向 canonical URL 加锚点。
7. 如果正文出现“如下图”“以上代码”“见下表”，必须存在对应图片说明、代码块或表格。无法恢复时视为内容缺失。
8. 不得根据标题或图片文件名臆造正文、代码、图片内容、作者、时间、版本、摘要或许可证。
9. 自动生成的摘要只能放入 `description`，不得在正文开头重复堆叠标题、摘要、关键词和 intro。
10. 每篇正文必须能脱离原网页导航独立阅读。

## 四、去重

1. 先规范化 URL，去除同一页面的参数变体和镜像。
2. 使用规范化正文的 SHA-256 做精确去重。
3. 使用 MinHash、SimHash 或 embedding 做近似去重。正文相似度超过 0.95 时保留质量、权威性和时效性更好的版本，并记录被合并 URL。
4. 同标题但正文不同的 API 重载或不同版本不能直接删除，必须通过签名、版本、分类和 canonical URL 区分。
5. 文档去重后再分块，分块后再次执行精确和近似去重。

## 五、语义分块

1. 使用 Markdown AST 或 DOM 结构按标题、段落和语义边界切分，禁止固定字符数硬切。
2. 目标长度为 300 至 700 tokens，硬上限 900 tokens。
3. 小于 120 tokens 的片段原则上与相邻同主题片段合并；独立定义、短公式或短代码可以作为有理由的例外。
4. 代码块、表格、公式和步骤列表保持原子性。超长时只能按其内部合法结构拆分。
5. 禁止在句子、URL、标识符、Markdown 链接、代码字符串或表格行中间截断。
6. 只对连续长 prose 使用 40 至 80 tokens 重叠，不机械重复标题、代码、表格或模板。
7. 标题和标题路径放在独立字段中，不要在每个 `content` 中重复堆叠。
8. 每个片段必须有直接来源 URL；能够定位章节时必须附带锚点。
9. 不生成 embedding。目标项目会使用自己的 embedding 模型统一建库。

## 六、最终交付目录

最终必须交付下面的完整目录。目录名中的时间使用 UTC：

xbots-kb-v2-YYYYMMDDTHHMMSSZ/
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

文件要求：

- 所有 JSONL 每行一个完整 JSON 对象，不使用跨行对象或一个超大 JSON 数组。
- 每个 JSONL 分片最多 1,000 条，按稳定 ID 排序。
- 所有文本使用 UTF-8 无 BOM 和 LF。
- 同一输入、同一抓取版本重复运行时，规范化输出和内容哈希应保持稳定。
- `checksums.sha256` 覆盖最终目录内除其自身外的全部交付文件。
- `README.md` 必须写明运行环境、依赖、抓取范围、重跑方式、校验命令、已知限制和失败恢复方法。

## 七、documents JSONL 格式

每行一篇完整清洗文档：

{
  "schema_version": "2.0",
  "document_id": "sha256:由规范化 canonical_url 生成的稳定ID",
  "canonical_url": "https://docs.example.com/topic/page",
  "source_domain": "docs.example.com",
  "source_name": "来源名称",
  "source_type": "official_documentation",
  "title": "不含站点后缀的准确标题",
  "description": "不超过300字且不与正文机械重复的摘要",
  "language": "zh-CN",
  "category": "python",
  "tags": ["sorting", "algorithm"],
  "content_markdown": "# 标题\n\n完整 Markdown 正文",
  "headings": [{"level": 1, "text": "标题", "anchor": "title"}],
  "published_at": null,
  "updated_at": "2026-07-01T00:00:00Z",
  "crawled_at": "2026-07-15T12:00:00Z",
  "content_version": null,
  "license": null,
  "http_status": 200,
  "content_sha256": "规范化 content_markdown 的 sha256"
}

约束：

- `document_id` 必须稳定，不能使用数据库自增 ID。
- `source_type` 使用受控枚举：`official_documentation`、`standard`、`academic`、`maintainer_documentation`、`maintainer_blog`、`tutorial`。
- `category` 使用统一小写 slug。
- `title` 不允许空值、`N/A`、纯序号或站点后缀。
- 未知字段使用 `null`，不能捏造。

## 八、chunks JSONL 格式

每行一个语义片段：

{
  "schema_version": "2.0",
  "chunk_id": "sha256:document-id#0001",
  "document_id": "sha256:稳定ID",
  "chunk_index": 0,
  "title": "文档标题",
  "heading_path": ["快速排序", "分区过程"],
  "content": "语义完整的片段正文",
  "language": "zh-CN",
  "category": "algorithms",
  "tags": ["quick-sort", "divide-and-conquer"],
  "source_url": "https://docs.example.com/quick-sort#partition",
  "source_domain": "docs.example.com",
  "source_type": "official_documentation",
  "content_version": null,
  "char_count": 428,
  "token_count": 312,
  "content_sha256": "片段正文 sha256"
}

`chunk_index` 必须从 0 连续递增。`source_url` 必须能直接打开原文或对应章节。`char_count`、`token_count` 和哈希必须由脚本重新计算并校验。

## 九、manifest 格式和报告

`manifest.json` 至少包含：

- `schema_version`
- `dataset_id`
- `generated_at`
- `crawler_name` 和 `crawler_version`
- `document_count`、`chunk_count`、`failure_count`、`deduplicated_count`
- `source_domain_count` 和各域名文档数量
- 分类、语言、来源类型和版本分布
- 清洗规则版本
- tokenizer 名称和版本
- 分块目标、上限、下限和重叠策略
- golden query 数量
- 所有验收指标汇总

`crawl_failures.jsonl` 每条至少包含 URL、阶段、错误类型、错误信息、重试次数、最终状态和时间。失败记录不能混入正式 documents/chunks。

## 十、必须执行的回归测试

你必须提供两个可独立运行的脚本，并实际运行它们。失败时退出码必须非 0。

### 1. validate_dataset.py

依次验证：

1. 所有 JSON/JSONL 可解析。
2. schema、必填字段、枚举和 ISO 8601 时间合法。
3. manifest 数量与实际行数一致。
4. document_id、chunk_id 全局唯一且稳定。
5. checksums 全部匹配。
6. 不存在 U+FFFD、BOM、零宽字符、非法控制字符和未解码 HTML 实体。
7. 不存在原始 HTML、站点短代码、导航、广告、页尾模板和抓取声明。
8. Markdown 可解析，代码围栏闭合，链接完整，表格结构有效。
9. “如下图、以上代码、见下表”等引用存在对应内容。
10. chunk_index 连续，片段不在句子、代码、表格、公式、URL 或 Markdown 链接中间截断。
11. token 长度符合规则，所有例外都有机器可读原因。
12. 精确重复文档和分块为 0，近似重复率低于 1%。
13. canonical_url 和 source_url 格式合法。
14. 对每个主要分类和来源随机抽样，总计至少 100 篇，生成人工抽查清单。

硬性门槛：JSON/schema/ID/checksum 通过率 100%；非法字符、原始短代码、模板污染、不闭合代码围栏、无理由结构截断和精确重复均为 0。

### 2. run_retrieval_regression.py

不依赖目标项目实现一个可重复的本地基线：至少测试 BM25；如果本地允许使用一个公开、固定版本的多语言 embedding 模型，则额外测试向量和混合检索，并在报告中记录模型名称、版本和维度。不要把测试 embedding 放进交付 chunks。

制作至少 100 条人工标注的 `golden_queries.jsonl`，覆盖：

- 概念解释。
- 精确 API 和命令。
- 代码问题。
- 中文、英文和中英混合查询。
- 同义词和口语表达。
- 版本敏感问题。
- 模糊查询。
- 知识库范围外的问题。
- 天气、新闻、价格等不应检索静态课程资料的问题。

每条格式：

{
  "query_id": "q-0001",
  "query": "Python 快速排序如何实现",
  "expected_document_ids": ["sha256:..."],
  "expected_categories": ["python", "algorithms"],
  "forbidden_document_ids": [],
  "should_retrieve": true,
  "notes": "应返回完整代码和复杂度说明"
}

输出 Recall@5、MRR@5、nDCG@10、无关结果率、范围外误检率、来源多样性、查询 P50/P95 和逐条失败案例。

建议门槛：混合检索 Recall@5 >= 0.85、MRR@5 >= 0.75、nDCG@10 >= 0.80；范围外误检率 <= 5%。如果没有运行向量模型，BM25 指标必须单独报告，不能伪造混合检索结果。

### 3. URL 与来源抽检

1. 校验全部 URL 格式。
2. 对至少 500 条分层抽样 URL 检查可访问性。
3. 对至少 100 条带锚点 URL 验证能定位对应章节。
4. 抽样可访问率应不低于 98%。因网络地域限制失败时单独分类，不得默认为内容有效。

### 4. 人工内容抽检

至少抽查 100 篇，覆盖全部主要分类、来源类型和高占比域名。逐篇检查标题、正文完整性、代码、表格、图片引用、版本、URL 和分块边界。严重内容缺失必须为 0，否则修复并重新执行完整测试。

## 十一、执行顺序

1. 创建工作目录和可恢复的抓取状态文件。
2. 输出 allowlist、分类覆盖和抓取计划。
3. 小规模抓取每个来源至少 5 页，先验证解析器质量。
4. 对小样本运行完整清洗和分块测试。
5. 修复解析器后再进行全量抓取，禁止带着已知解析错误扩大数据量。
6. 执行 URL 规范化、文档去重和质量过滤。
7. 生成 documents。
8. 语义分块并生成 chunks。
9. 生成至少 100 条人工标注查询。
10. 运行全部验证和检索回归。
11. 对失败案例修复后重新生成数据，并再次运行全套测试。
12. 最后生成 manifest、报告和 checksums。

## 十二、完成标准

只有在所有硬性检查通过后才能声明完成。最终回复必须明确给出：

1. 最终数据包的绝对路径。
2. 文档数、分块数、来源域名数、分类数、失败数和去重数。
3. 每个来源域名的占比，特别说明是否超过 35%。
4. Schema、编码、清洗、Markdown、分块、去重、URL、人工抽查的通过/失败数量。
5. Recall@5、MRR@5、nDCG@10、范围外误检率和查询 P95。
6. 仍未解决的风险和失败页面数量，不得隐瞒或以“基本可用”代替数据。
7. 明确声明没有访问或修改 XBots 项目、正式数据库和旧知识库。

不要在数据尚未通过测试时提前结束；不要只提供代码而不运行；不要只给测试日志而不交付数据；不要将缓存、虚拟环境、模型权重、浏览器缓存或临时 HTML 混入最终数据包。
```

## 转交回来时需要提供的信息

外部 Agent 完成后，请将以下内容一起转交给 XBots 项目：

1. 完整的 `xbots-kb-v2-*` 目录，不要只取 `documents` 或 `chunks`。
2. 外部 Agent 的最终测试摘要。
3. 抓取过程中使用的 Python 和主要依赖版本。
4. 如果目录过大，可以压缩，但解压后目录结构和校验和必须保持不变。
5. 不需要外部 Agent 提供 MySQL SQL、Chroma 数据目录或 XBots 项目补丁。
