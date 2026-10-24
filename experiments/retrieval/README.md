# K1 中文检索基线评测

本目录是独立实验，不是生产搜索入口。不导入应用store、不改业务数据库、不调用模型、不安装新包。

## 复跑

在项目根目录执行：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_retrieval_eval -v
.venv\Scripts\python.exe experiments/retrieval/evaluate.py
.venv\Scripts\python.exe experiments/retrieval/probe.py --queries runtime/k1/user-queries.json
```

依赖本机既有10份私有原文快照。cases_v1.json仅含自拟问题、源hash/块ID/字符范围/摘录hash，不附正文；换电脑缺语料不能复现真实成绩，测试使用自己编写的短夹具，不冒充真实检索评测。源码中没有原文快照。freeze.py需要私有spec文件且显式指定输出；源快照变化时evaluate拒绝继续，不会自动重标。不要覆盖v1后宣称旧留出集仍是盲测。

- 30个自拟候选问题，24个有已标注位置、6个本次文字语料无答案，dev/heldout各15。作者编题且看过全部问题，不是第三方盲测；标签未获用户确认，ASR意图4题还需听校。
- 指标：Success@5（至少一个已标注位置命中）、来源Success@5、已知标注MRR@5；没有完整相关性标注，不把它叫完整Recall或Precision。
- 无答案题的非空候选数只描述检索噪声；没有自动回答，因此不能算答案幻觉率或已实现拒答。
- 标题和正文literal为整条输入的子串匹配，对应最基础的现有式搜索，不代表成熟关键词检索。trigram和bigram以查询词元OR召回，SQLite bm25排序；bi另测每来源最多两条。双字索引保存重复词元频次，不把文档变成set；查询词元去重。
- NFKC/casefold在建索引时缓存，所有词法方法相同输入。性能优化后150个query/method组合Top5与首轮完全一致，没有根据留出结果调排序。延迟为每题7次热查询中位数再计算分位值，不是HTTP/冷启动/大规模库尾延迟。
- 分词只覆盖本轮常用CJK字块和英文/数字词，不宣称覆盖全部罕见汉字；文章沿用既有可见文字块，图片/OCR和导入时丢失的正文不在检索范围。
- 内存SQLite页大小包含trigram与bigram两个索引；不是单一生产索引大小或进程总内存。

原文、人工复核材料、四个用户原始问题及结果放runtime/k1，不提交Git。USER_PROBES仅保留query_hash和位置元数据，未回填30题。标签仍待确认，不能将用户探针自动计入准确率。

方案来源、本站取舍见K1_EVAL_PLAN_20261024.md；指标/局限/下一步见K1_EVAL_MILESTONE_20261024.md。
