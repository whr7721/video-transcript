"""Frozen lexical baselines, implemented with the bundled SQLite FTS5."""
import re
import sqlite3
import unicodedata

METHODS=('title_literal','body_literal','trigram_bm25','bigram_bm25','bigram_diverse')


def normalize(text):return unicodedata.normalize('NFKC',text).casefold()


def terms(text,n,unique=True):
 result=[]
 for word in re.findall(r'[\u3400-\u9fff]+|[a-z0-9_]+',normalize(text)):
  if re.fullmatch('[a-z0-9_]+',word):result.append(word)
  elif len(word)>=n:result.extend(word[i:i+n] for i in range(len(word)-n+1))
 return list(dict.fromkeys(result)) if unique else result


class Baselines:
 def __init__(self,passages):
  self.passages=passages;self.db=sqlite3.connect(':memory:')
  self.normalized={p['id']:{'title':normalize(p['title']),'text':normalize(p['text'])} for p in passages}
  self.db.execute('CREATE VIRTUAL TABLE tri USING fts5(text, tokenize="trigram")')
  self.db.execute('CREATE VIRTUAL TABLE bi USING fts5(text)')
  for i,p in enumerate(passages,1):
   self.db.execute('INSERT INTO tri(rowid,text) VALUES (?,?)',(i,self.normalized[p['id']]['text']))
   self.db.execute('INSERT INTO bi(rowid,text) VALUES (?,?)',(i,' '.join(terms(p['text'],2,unique=False))))

 def search(self,query,method,k=5):
  if method not in METHODS:raise ValueError('Unknown baseline')
  if not isinstance(query,str) or not query.strip() or len(query)>200:raise ValueError('Query must be 1..200 characters')
  if type(k) is not int or not 1<=k<=50:raise ValueError('Invalid k')
  q=normalize(query).strip()
  if method in ('title_literal','body_literal'):
   field='title' if method=='title_literal' else 'text'
   hits=[];seen=set()
   for p in self.passages:
    if q in self.normalized[p['id']][field] and (field!='title' or p['source_uid'] not in seen):
     hits.append({**p,'score':1.0,'coverage':1.0});seen.add(p['source_uid'])
   # Title match can locate a source, but its first passage is not automatically relevant.
   return sorted(hits,key=lambda p:p['id'])[:k]
  n=3 if method=='trigram_bm25' else 2
  tokens=terms(q,n)
  if not tokens:return []
  expression=' OR '.join('"'+t.replace('"','""')+'"' for t in tokens)
  table='tri' if n==3 else 'bi'
  rows=self.db.execute(f'SELECT rowid,bm25({table}) FROM {table} WHERE {table} MATCH ? ORDER BY bm25({table}),rowid LIMIT 50',(expression,)).fetchall()
  result=[];counts={}
  for rowid,score in rows:
   p=self.passages[rowid-1];uid=p['source_uid']
   if method=='bigram_diverse' and counts.get(uid,0)>=2:continue
   counts[uid]=counts.get(uid,0)+1
   coverage=sum(t in self.normalized[p['id']]['text'] for t in tokens)/len(tokens)
   result.append({**p,'score':-score,'coverage':coverage})
   if len(result)==k:break
  return result

 def close(self):self.db.close()
