# ASR 英文专名纠正说明

SenseVoice 对英文专有名词的音译噪声（`deep sickick` / `harnes` / `honess` / `snluma` / `snow鲁码`）会污染搜索、引用和切片字幕。这里在转写结果上做一层可控、可回滚的纠正，不碰模型、不加依赖。

## 为什么不走原生热词

- 本机 `sherpa-onnx 1.13.8`：`OfflineRecognizer.from_sense_voice()` 的签名里**没有** `hotwords_file` / `hotwords_score`，只有 `from_transducer()` 有。
- 官方文档（https://k2-fsa.github.io/sherpa/onnx/hotwords/index.html）写明：只有 transducer 模型支持热词，且必须用 `modified_beam_search`；其它模型（Paraformer / Whisper / SenseVoice…）都不支持。
- 该版本 SenseVoice 工厂确实暴露 `hr_dict_dir` / `hr_rule_fsts` / `hr_lexicon`（同音替换），但那是面向中文拼音的音节级替换，需要模型专属词典，处理不了"多个英文词被连读成一个中文音译"的情况，也无法计数与回溯。

结论：走**后处理纠正层**。详见 `RESEARCH_DECISIONS.md` 同日条目。

## 怎么用

词表在 `data/hotwords.json`，**首次转写时自动生成**，之后自己改：

```json
{
 "_说明": "键是规范写法，值是识别变体（大小写/空格/标点不敏感）；改完下一条转写生效。",
 "DeepSeek": ["deep sickick", "deep sick", "deeps", "dedes"],
 "harness": ["harnes", "honess", "harnessness", "哈nes"],
 "SnoLuma": ["snluma", "snoluma", "snow luer", "snowluer", "snow鲁码", "snow鲁马", "snow路码", "snow撸码"]
}
```

- 键是**替换成什么**（规范写法），值是**可能被识别成什么**（变体）。
- 键大小写不敏感并与默认表合并；只写 `"Qwen": ["quen model"]` 就能追加，不用重抄默认项。
- 匹配规则：忽略大小写、空格、标点；长变体优先；拉丁字母边界保护（`harnes` 不会把 `harness` 吃成 `harnesss`）；重叠命中只取一个。
- 没命中的文本原样不动；OCR 图文也会过一次这层，通常是 0 命中。

## 原稿纪律

一次纠正会在 `transcript.json` 里留下三样东西：

| 字段 | 含义 |
|---|---|
| `text` / `segments` | 展示稿与下游（搜索、切片、二创）使用的**已纠正**文本 |
| `raw_text` | 未纠正的原始识别，逐字保留，可回溯 |
| `corrections` | 明细：`[{term, variants:{变体:次数}, count}]`，`review_note` 追加"已按专名表纠正 N 处英文专名" |

`corrections` 一旦存在就跳过再次纠正，重复导出不会叠加替换；转写的分段缓存仍保存原始识别，改词表后重跑导出即可得新结果。

## 接入点

- `link_ingest.export()`：链接、本地文件、图文稿的统一出口。
- `transcript_stage.finish_transcription()`：视频与云端 ASR，在写 `transcript.json/.txt/.md` 之前。

## 实测（runtime/hotwords-20261101/）

| 场景 | 结果 |
|---|---|
| 历史转写重放 `44dddd1bae6dab54`（"把 DeepSeek 大肥鱼接入 QQ"，1925 字） | 纠正 **14 处**（SnoLuma 6 / harness 6 / DeepSeek 2），`raw_text` 与原文逐字一致，原稿字节未变，纠正后**零残留** |
| 同一条历史任务 `254234f520f18d2b`（用户给的样例 ID） | **0 命中**——该任务是"人生哲学"，全文无英文专名；真正噪声在 `44dddd1bae6dab54` |
| 同一段音频**重新 ASR**（隔离目录，1929 字/18 段） | 原文命中全部变体类别，纠正 **12 处**，导出后 `transcript.json` 带 `raw_text`+`corrections`，零残留，`transcript.txt` 与 json 一致 |
| 单测 | `tests/test_asr_hotwords.py` 11 条：归一化/边界/长优先/CJK 相邻/空文本、raw 保留与幂等、词表合并、词表落盘、export 与 finish_transcription 两个接入点 |

## 边界

- 只替换词表里的变体；表外的新噪声不会被猜。"DeepSeek 被读成别的音"需要你把它加进变体列表。
- 不做翻译、不做改写，只换写法；专名大小写以词表键为准（`harness` 小写、`DeepSeek`/`SnoLuma` 品牌写法）。
- 同音字变体（`snow鲁码`/`snow路码`）依赖词表穷举，不是拼音推断。
- 已完成的旧转写不会自动重写：重放或重新导出才会应用新词表。
