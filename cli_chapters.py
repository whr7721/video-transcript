"""CLI rendering over the existing checkpointed semantic chapter jobs."""
import time
import chapter_jobs,chapters,cli_summary,store

def summarize(ident):
    task=store.get(ident)
    if not task:raise ValueError('转写任务不存在')
    view=chapters.snapshot(task)
    key=chapter_jobs.digest([chapter_jobs.VERSION,chapter_jobs.organizer.MODEL,ident,view['source_hash'],'directory',chapter_jobs.DIRECTORY_VERSION])
    job=chapter_jobs.get(key)
    if not job or job['status']!='completed':
        job=chapter_jobs.start(task,'directory',chapters.get(task)['revision'])
        try:
            while job['status'] in {'queued','running'}:
                time.sleep(.2);job=chapter_jobs.get(job['id'])
        except KeyboardInterrupt:
            chapter_jobs.cancel(job['id']);raise
    if job['status']!='completed':raise RuntimeError(job.get('error') or '章节导读未完成；原稿和摘要已保留，可显式重试')
    if chapters.snapshot(store.get(ident))['source_hash']!=view['source_hash']:raise ValueError('原稿已改变，未导出旧章节')
    plan=job['plan'];lines=['# 章节导读','> AI按话题分章，引用供回查，不代表人工质量核验。','']
    for i,section in enumerate(plan['sections']):
        selected=chapters.resolve(view,plan,i)
        lines+=['## '+section['title'],section.get('guide','')]
        ids=list(dict.fromkeys(r['source_id'] for r in selected['ranges']))
        lines+=['来源：'+cli_summary.source_label(ids,view['sources']),'']
    text='\n'.join(lines);cli_summary.atomic_text(store.DATA/'jobs'/ident/'chapters.md',text)
    return text
