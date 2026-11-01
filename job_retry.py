"""Retry 的公共三步：重置记录状态、落库、交回队列。

link_jobs / local_files / podcasts / private_images 的 retry 守卫本来不同（404 文案、
允许重试的状态集、link_jobs 还要处理任务双记录），所以只合并完全相同的这三步，
守卫留在各自路由里，不另造 dispatch 抽象。
"""


def requeue(record, save, enqueue, **fields):
    record.update({'error': None, **fields})
    save(record)
    enqueue()
    return record
