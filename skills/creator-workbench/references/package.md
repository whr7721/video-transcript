# 作品交接格式

每篇目录保存brief.md、manifest.json、title.txt、正文.md、images/、music.md。无需新数据库。

manifest最小例：
```json
{"schema_version":1,"id":"20261110-low-valley","platform":"douyin","expected_images":4,"title_file":"title.txt","caption_file":"正文.md","images":["images/01.png","images/02.png","images/03.png","images/04.png"],"sources":[],"music":{"status":"track_confirmed","title":"Back in Time","artist":"Borrtex","platform_url":null},"steps":{"intake":"completed","editorial":"completed","images":"completed","music":"partial"},"reviews":["已读完整原稿，核对作者归属和四张图中文字；纯配乐入口待核实"]}
```

sources接受脚本ingest输出的source对象，或活动记录：kind=activity，platform/id/url/captured_at/rules_path/rules_verified。保留原始规则路径，不把热度/机会分当完整规则。来源记录不能带Cookie、Authorization或会话存储。

music.status：platform_confirmed=实际核对可选的纯伴奏；track_confirmed=仅确认曲名作者；unverified=尚未核实；not_requested=本次不配乐。原声可能含人声，另在music.md说明。

reviews由宿主实际读稿、看图后填写，不由文件检查器自动补。图片数以单篇brief/活动要求为准，默认四张不是所有平台硬规则。pack当前检测PNG与3:4、缺文件、重复图片和原稿哈希；不做OCR或内容真伪判定。

断点恢复直接读取manifest.steps和文件；不因换对话重复调用模型。脚本不会生成正文、挑曲或调用任何AI。
