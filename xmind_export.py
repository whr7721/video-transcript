"""Zero-call conversion of the validated map to modern XMind JSON ZIP."""
import io,json,uuid,zipfile
import mindmap

def export(root):
 root=mindmap.validate({'root':root})
 def topic(n):
  return {'id':uuid.uuid4().hex,'class':'topic','title':n['text'],'children':{'attached':[topic(c) for c in n.get('children',[])]}}
 files={'content.json':[{'id':uuid.uuid4().hex,'class':'sheet','title':root['text'],'rootTopic':topic(root)}],'metadata.json':{'creator':{'name':'拾文'},'dataStructureVersion':'3','layoutEngineVersion':'5'},'manifest.json':{'file-entries':{'content.json':{},'metadata.json':{}}}}
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in files.items():z.writestr(name,json.dumps(data,ensure_ascii=False))
 return out.getvalue()
