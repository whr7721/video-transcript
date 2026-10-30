"""Small offline bilingual vocabulary; query-only expansion, never a translation API."""
import re,unicodedata
VOCAB=(
 ('人工智能','artificial intelligence','ai'),('机器学习','machine learning','ml'),('深度学习','deep learning'),
 ('神经网络','neural network'),('大语言模型','large language model','llm'),('知识库','knowledge base'),
 ('向量数据库','vector database'),('检索增强生成','retrieval augmented generation','rag'),
 ('思维导图','mind map','mindmap'),('提示词','prompt'),('语音识别','speech recognition','asr'),
 ('转写','transcription','transcript'),('播客','podcast'),('订阅','subscription'),('隐私','privacy'),
 ('简历','resume','résumé'),('面试','interview'),('编程','programming'),('软件开发','software development'),
 ('数据库','database'),('摄影','photography'),('心理学','psychology'),('经济学','economics'),
 ('投资','investment','investing'),('营养','nutrition'),('健康','health'),('旅行','travel'),
 ('学习率','learning rate'),('时间管理','time management'),('批判性思维','critical thinking'))
def phrases(query):
 q=unicodedata.normalize('NFKC',query).casefold();out=[q]
 for group in VOCAB:
  def contains(p):
   p=p.casefold()
   return p in q if re.search(r'[\u3400-\u9fff]',p) else bool(re.search(r'(?<![a-z0-9_])'+re.escape(p)+r'(?![a-z0-9_])',q))
  if any(contains(p) for p in group):out.extend(group)
 return list(dict.fromkeys(out))
