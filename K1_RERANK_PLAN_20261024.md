# K1-E1 重排对照方案 · 2026-10-24

用户已确认K1-E0通过，并要求查询约束、词法重排、轻量语义重排比较；paraphrase逐题单列，失分集中则升级语义候选。向量库继续暂缓。此轮仍为独立实验，不改R2业务代码或生产依赖，不默认将实验胜者接入网站。

## 固定比较设计（运行新排名前记录）

- 同一v1题集/语料/500字片段及同一BM25 Top50；不额外放入正例，不用AI导读或期望答案扩充候选。v1此前留出已看过，本轮只能叫重复回归，不能再称全新盲测。
- 方法：原BM25、硬查询约束、词法重排、轻量Cross-Encoder语义重排。约束只用通用功能词移除、显式ASCII实体必须出现、有效查询词元覆盖至少1/3；无查询专用别名或ASR猜词。词法分数固定为0.45归一BM25+0.45语料IDF覆盖+0.10显式实体覆盖；不根据留出结果反复调参。
- 语义模型：官方cross-encoder/mmarco-mMiniLMv2-L12-H384-v1，revision 1427fd652930e4ba29e8149678df786c240d8825，Apache-2.0，多语言含中文。选官方ONNX AVX2 INT8文件118620016字节，固定SHA256，tokenizer同样固定。CPU本地执行，4线程，不下载Torch，不发送用户原文至服务，不建向量库。
- 模型和依赖只进runtime/k1-rerank，独立venv的onnxruntime==1.23.2/tokenizers==0.22.2；不改现有requirements或ASR环境。模型分数不叫校准概率或事实正确率。
- 所有方法只改顺序/过滤，保留不可变原文范围。模型512 token上下文不静默截断：过长候选分成覆盖全部文字的重叠窗口，取最高相关度并记录子窗口数；最大查询超过预算则拒绝，不截掉问题。原始候选及引用始终完整。
- 指标沿用范围/来源Success@5、已知标注MRR、正例候选池覆盖、无答案题非空候选数；另记过滤误伤、paraphrase逐题排名与得失、延迟、下载/启动开销及模型/依赖体积。
- 四个用户真实问题单独probe，保留其未审标注身份，不能与v1合并制造漂亮总分。凡是只有部分相关或缺直接证据，不算“已回答”。

## 原始来源与取舍

- 官方Retrieve & Re-Rank文档：https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html 。采用候选召回后Cross-Encoder评分机制；不引入完整SentenceTransformers/Torch栈。
- 官方小模型卡：https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 ，官方repo提供ONNX量化文件并列出Apache-2.0。固定revision/LFS SHA，避免执行远端自定义代码。
- BAAI bge-reranker-base/v2-m3官方卡为候选，中文适配值得后续对照，但本轮小模型更省下载和CPU资源；不因模型卡宣传直接承诺本站效果。
- Jina官方模型文档说明多语言能力，但本地权重商用许可条件需另核，且本轮不需要新增服务/Key，故不采用。

## 决策门

必须单列4个paraphrase问题，每题展示原排名、约束/词法/语义排名和池内有无已标注范围。说明失分是否集中、是否仅并列、样本是否过少；集中时语义重排进入候选，而非自动上线。语义若修复同义查询却伤害短词或ASR题，必须并列报告。先排除语料缺失和标注不完整，不能以“分数高”冒充答案充分。
