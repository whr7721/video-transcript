# K1-E1：查询约束与轻量语义重排实验

本目录不属于生产搜索或发行白名单。沿用K1-E0冻结语料、题集与BM25 Top50，候选原文/引用不改变，不新增向量库。用户问题和逐条原文只留runtime。

## 固定方法

- bm25：原双字/英文词BM25。
- constraints：移除通用问法功能词后，要求显式ASCII实体出现且有效查询词元覆盖≥1/3。没有查询专用别名，过滤后为空不偷偷回退。
- lexical_rerank：固定0.45归一BM25+0.45语料IDF词元覆盖+0.10实体覆盖。
- semantic_rerank：官方mmarco-mMiniLMv2-L12-H384-v1 INT8 Cross-Encoder，对相同Top50评分。原始logit不等于正确率。评分只影响排名，不生成答案，也不判断证据充分。

v1留出在E0已经看过，本轮为固定题集回归，不称新盲测。没有根据本轮结果修改规则/权重，也没有把已知正例塞回池中。

## 环境与模型

使用独立runtime/k1-rerank/venv，不改主venv与requirements。直接依赖onnxruntime1.23.2、tokenizers0.22.2，完整冻结版本见requirements-experiment.lock.txt。模型与tokenizer仅在runtime，MANIFEST记录官方revision、大小、LFS SHA256；下载时验证后原子替换，加载时再核验。代码不执行远端自定义代码或pickle，不读取用户Key。

模型来源：https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 ，Apache-2.0，多语言含中文，训练源为机器翻译MMARCO；不能据此保证中文口播/ASR质量。ONNX Runtime与Tokenizers通过PyPI安装，仅实验环境新增依赖，权重不随仓库分发。

512 token预算下，过长候选用覆盖全部文档token的重叠窗口打分取max，不静默截掉尾部；长问题超预算拒绝。所有原文引用仍指向完整原始片段。CPU4线程、无GPU/Torch、禁用ORT telemetry。本轮代码只从本地文件加载推理，不调用远程模型API。

## 复跑（Windows，在项目根目录）

```powershell
.venv\Scripts\python.exe -m venv runtime\k1-rerank\venv
runtime\k1-rerank\venv\Scripts\python.exe -m pip install -r experiments\retrieval_rerank\requirements-experiment.lock.txt
.venv\Scripts\python.exe experiments\retrieval_rerank\fetch_model.py
runtime\k1-rerank\venv\Scripts\python.exe experiments\retrieval_rerank\check_model.py
runtime\k1-rerank\venv\Scripts\python.exe experiments\retrieval_rerank\run_comparison.py
runtime\k1-rerank\venv\Scripts\python.exe experiments\retrieval_rerank\probe_comparison.py
```

真实语料仍依赖原机器私有快照；没有随包附上或冒充跨机器复现。probe额外需要runtime/k1/user-queries.json。比较输出只有ID/hash/指标，原文结果写runtime/k1-rerank/review.json及user-review.json。

新增控制逻辑测试：`.venv\Scripts\python.exe -m unittest tests.test_rerank_eval -v`，主环境无需安装语义包。模型集成检查须在独立环境执行，不用mock替代真实推理。

报告：PARAPHRASE_20261024.md逐题列出改写类；RESULTS列全部方法/类别/逐题；USER_PROBES仅记用户query_hash及潜在相关来源位置（不是已确认答案）；MODEL_CHECK记录模型边界检查；最终取舍见K1_RERANK_MILESTONE_20261024.md。
