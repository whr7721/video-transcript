"""Fixed query constraints and lexical reranking; no query-specific aliases."""
import math,re
from experiments.retrieval import baselines
VERSION='rerank-controls-v1'
STOP=('为什么','有没有','告诉我','如何','怎样','怎么','什么','哪些','是否','可以','应该','请问','我们','这个','一个')


def query_parts(query):
 q=baselines.normalize(query)
 cleaned=q
 for word in sorted(STOP,key=len,reverse=True):cleaned=cleaned.replace(word,' ')
 tokens=baselines.terms(cleaned,2)
 anchors=re.findall(r'[a-z][a-z0-9_]*(?:[.-][a-z0-9_]+)*',cleaned)
 return tokens,list(dict.fromkeys(anchors))


def anchor_present(text,anchor):
 return bool(re.search(r'(?<![a-z0-9_])'+re.escape(anchor)+r'(?![a-z0-9_])',text))


class Controls:
 def __init__(self,passages):
  self.text={p['id']:baselines.normalize(p['text']) for p in passages}
  self.df={}
  for p in passages:
   for token in baselines.terms(p['text'],2):self.df[token]=self.df.get(token,0)+1
  self.count=len(passages)

 def features(self,query,pool):
  tokens,anchors=query_parts(query)
  weights={t:math.log(1+(self.count+1)/(self.df.get(t,0)+1)) for t in tokens}
  total=sum(weights.values()) or 1
  maximum=max((p['score'] for p in pool),default=1) or 1
  rows=[]
  for p in pool:
   text=self.text[p['id']]
   coverage=sum(t in text for t in tokens)/len(tokens) if tokens else 0
   weighted=sum(w for t,w in weights.items() if t in text)/total
   anchor_ratio=sum(anchor_present(text,a) for a in anchors)/len(anchors) if anchors else 1
   rows.append({**p,'query_coverage':coverage,'weighted_coverage':weighted,'anchor_ratio':anchor_ratio,
                'lexical_score':.45*p['score']/maximum+.45*weighted+.10*anchor_ratio})
  return rows

 def rank(self,query,pool,method):
  if method not in ('constraints','lexical_rerank'):raise ValueError('Unknown control method')
  rows=self.features(query,pool)
  if method=='constraints':return [p for p in rows if p['anchor_ratio']==1 and p['query_coverage']>=1/3]
  return sorted(rows,key=lambda p:(-p['lexical_score'],p['id']))
