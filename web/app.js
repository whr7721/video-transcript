'use strict';
const $ = (id) => document.getElementById(id);
const state = { tasks: [], selected: null, current: null, provider: 'local', polling: false, toastTimer: null };
const statusNames = {queued: '等待处理', running: '处理中', completed: '已完成', failed: '需重试', processing: '批量处理中', partial: '部分失败', paused: '已暂停', skipped: '已跳过'};

async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, {...options, headers: {'Content-Type': 'application/json', ...(options.headers || {})}}); }
  catch { throw new Error('暂时连接不到本地服务。请检查拾文是否正在运行，页面内容已保留。'); }
  let body;
  try { body = await response.json(); } catch { throw new Error('本地服务没有返回有效结果，请稍后重试。'); }
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : '请求未完成，请检查输入后重试。');
  return body;
}

function icon(name, className = '') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('aria-hidden', 'true');
  if (className) svg.setAttribute('class', className);
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#i-${name}`); svg.append(use); return svg;
}

function toast(message) {
  clearTimeout(state.toastTimer); $('toast').textContent = message; $('toast').hidden = false;
  state.toastTimer = setTimeout(() => {$('toast').hidden = true;}, 4200);
}

function duration(seconds) {
  if (!seconds) return '';
  const total = Math.floor(seconds); return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

function characters(text) { return Array.from(text.replace(/\s/g, '')).length; }

function renderHistory() {
  const search = $('search').value.trim().toLowerCase();
  const tasks = state.tasks.filter(t => `${t.title || ''} ${t.author || ''}`.toLowerCase().includes(search));
  $('taskCount').textContent = String(state.tasks.length);
  const fragment = document.createDocumentFragment();
  if (!tasks.length) {
    const p = document.createElement('p'); p.className = 'history-empty';
    p.textContent = search ? '没有找到匹配的文稿。' : '第一份文稿，从一个链接开始。'; fragment.append(p);
  }
  for (const task of tasks) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = `history-item${state.selected === task.id ? ' selected' : ''}`;
    if (state.selected === task.id) button.setAttribute('aria-current', 'true');
    button.append(icon('file', 'history-icon'));
    const content = document.createElement('div');
    const title = document.createElement('div'); title.className = 'history-title'; title.textContent = task.title || '正在读取视频信息';
    const subtitle = document.createElement('div'); subtitle.className = 'history-subtitle';
    const date = document.createElement('span'); date.textContent = new Date(task.created_at * 1000).toLocaleDateString('zh-CN', {month:'2-digit',day:'2-digit'});
    const status = document.createElement('span'); status.className = task.status === 'completed' ? 'done' : task.status === 'failed' ? 'failed' : '';
    status.textContent = statusNames[task.status] || task.status;
    subtitle.append(date, status); content.append(title, subtitle); button.append(content);
    button.addEventListener('click', () => selectTask(task.id)); fragment.append(button);
  }
  // Avoid replacing a keyboard-focused history item on every polling tick.
  if (!$('history').contains(document.activeElement)) $('history').replaceChildren(fragment);
}

function renderText(text) {
  const view = $('transcript');
  if (view.dataset.text === text) return;
  view.dataset.text = text;
  const fragment = document.createDocumentFragment();
  for (const paragraph of text.split(/\n\s*\n/).filter(Boolean)) {
    const p = document.createElement('p');
    let cursor = 0;
    // Surface acronyms for review without silently "fixing" the speaker's words.
    for (const match of paragraph.matchAll(/[A-Za-z][A-Za-z0-9+.#-]{1,14}/g)) {
      p.append(document.createTextNode(paragraph.slice(cursor,match.index)));
      const term = document.createElement('abbr');term.className = 'review-word';term.textContent = match[0];
      term.title = '英文缩写或术语，建议回听核对；不代表已确认错误';p.append(term);
      cursor = match.index + match[0].length;
    }
    p.append(document.createTextNode(paragraph.slice(cursor)));fragment.append(p);
  }
  view.replaceChildren(fragment);
}

function renderTask(task) {
  state.current = task;
  const isBatch = task?.kind === 'creator';
  $('batchPanel').hidden = !isBatch; $('singlePanel').hidden = isBatch;
  $('backBatch').hidden = !task?.parent_id || isBatch;
  if (isBatch) { renderBatch(task); return; }
  const text = task?.result?.text || task?.partial_text || '';
  const hasTask = Boolean(task);
  $('emptyDocument').hidden = hasTask;
  $('documentContent').hidden = !hasTask;
  $('copyButton').disabled = !text;
  $('exportMenu').querySelector('summary').setAttribute('aria-disabled', task?.status === 'completed' ? 'false' : 'true');
  $('documentAuthor').textContent = task?.author || '正在读取作者';
  $('documentDuration').textContent = task?.duration ? `视频 ${duration(task.duration)}` : '';
  $('documentChars').textContent = text ? `${characters(text).toLocaleString()} 字` : '';
  $('documentTitle').textContent = task?.title || '';
  $('characterCount').textContent = `${characters(text).toLocaleString()} 字`;
  $('saveStatus').textContent = task?.status === 'completed' ? '已保存到本机 · 保留完整来源' : task?.status === 'running' ? '片段自动保存，刷新页面不影响处理' : task?.status === 'failed' ? '已保留素材与完成片段，可继续重试' : '等一份值得留下的内容';
  $('draftNotice').hidden = !hasTask || ['completed','failed'].includes(task.status);
  $('reviewNote').hidden = !text;
  renderText(text);
  $('sourceTitle').textContent = task?.title || '等待添加视频';
  $('sourceAuthor').textContent = task?.author || '从声音到文字，保留完整语境。';
  $('statusBox').textContent = task?.error || task?.message || '准备好链接，就可以开始。';
  $('statusBox').classList.toggle('error', task?.status === 'failed');
  $('retryButton').hidden = task?.status !== 'failed';
  if (task?.video_id) {
    $('sourceLink').href = `https://www.douyin.com/video/${task.video_id}`; $('sourceLink').hidden = false;
  } else { $('sourceLink').hidden = true; $('sourceLink').removeAttribute('href'); }
  const mediaReady = task && task.media_available !== false && ['preparing', 'transcribing', 'completed'].includes(task.stage);
  $('videoPlaceholder').hidden = Boolean(mediaReady); $('videoPlayer').hidden = !mediaReady;
  const videoSrc = mediaReady ? `/api/tasks/${task.id}/media` : '';
  if (videoSrc && $('videoPlayer').getAttribute('src') !== videoSrc) $('videoPlayer').src = videoSrc;
  if (!videoSrc && $('videoPlayer').hasAttribute('src')) { $('videoPlayer').pause(); $('videoPlayer').removeAttribute('src'); $('videoPlayer').load(); }
  const stepIndex = !task ? -1 : ['queued','resolving','fetching','downloading'].includes(task.stage) ? 0 : ['preparing','transcribing'].includes(task.stage) ? 1 : task.status === 'completed' ? 3 : -1;
  $('steps').querySelectorAll('li').forEach((li,index) => {li.classList.toggle('done',index < stepIndex);li.classList.toggle('current',index === stepIndex);});
  renderElapsed();
}

function renderElapsed() {
  const task = state.current;
  if (!task) { $('elapsed').textContent = '—'; return; }
  if (task.elapsed_seconds != null) {
    $('elapsed').textContent = `用时 ${task.elapsed_seconds < 60 ? `${Math.round(task.elapsed_seconds)} 秒` : duration(task.elapsed_seconds)}`;
  } else if (task.status === 'running' && task.started_at) {
    $('elapsed').textContent = duration(Date.now() / 1000 - task.started_at);
  } else { $('elapsed').textContent = statusNames[task.status] || '—'; }
}

async function selectTask(id) {
  state.selected = id; localStorage.setItem('shiwen-selected', id);
  const url = new URL(location.href); url.searchParams.set('task',id); history.replaceState(null,'',url);
  try {
    const task = await api(`/api/tasks/${id}`);
    if (state.selected !== id) return;
    renderTask(task); renderHistory();
    $('sidebar').classList.remove('open'); $('menuButton').setAttribute('aria-expanded', 'false');
  } catch(error) { toast(error.message); }
}

async function refresh() {
  if (state.polling) return;
  state.polling = true;
  try {
    state.tasks = await api('/api/tasks'); renderHistory();
    if (state.selected) {
      const selected = state.selected;
      const task = await api(`/api/tasks/${selected}`);
      if (selected === state.selected) renderTask(task);
    }
    $('engineBadge').title = '';
  } catch(error) { $('engineBadge').title = error.message; }
  finally { state.polling = false; }
}

$('captureForm').addEventListener('submit', async event => {
  event.preventDefault(); $('formError').hidden = true; $('shareInput').removeAttribute('aria-invalid');
  const input = $('shareInput').value.trim();
  if (!input) { $('formError').textContent = '先粘贴一个抖音视频链接。'; $('formError').hidden = false; $('shareInput').setAttribute('aria-invalid','true'); $('shareInput').focus(); return; }
  $('submitButton').disabled = true;
  $('submitButton').setAttribute('aria-busy','true');
  $('submitButton').firstChild.textContent = '正在提交…';
  try {
    const batch = $('captureMode').value === 'batch';
    const task = await api(batch ? '/api/batches' : '/api/tasks', {method:'POST',body:JSON.stringify({share_text:input,provider:state.provider,limit:Number($('batchLimit').value),max_duration_sec:Number(document.querySelector('input[name="maxDuration"]:checked').value),keep_media:$('keepMedia').checked})});
    await refresh(); await selectTask(task.id);
    toast(task.cached ? task.status === 'completed' ? '已找到这条视频的文稿，无需重复识别。' : '已打开这条视频的任务。' : '任务已添加，可以继续浏览已有文稿。');
  } catch(error) {
    $('formError').textContent = error.message; $('formError').hidden = false;
    $('shareInput').setAttribute('aria-invalid','true'); $('shareInput').focus();
  } finally { $('submitButton').disabled = false; $('submitButton').removeAttribute('aria-busy'); $('submitButton').firstChild.textContent = $('captureMode').value === 'batch' ? '开始批量提取' : '提取全文'; }
});
$('shareInput').addEventListener('input', () => {$('shareInput').removeAttribute('aria-invalid'); $('formError').hidden = true;});
$('sampleButton').addEventListener('click', () => {$('shareInput').value = 'https://v.douyin.com/Dv4LnzQVp8E/'; $('shareInput').focus();});
$('newTask').addEventListener('click', () => {
  state.selected = null; state.current = null; localStorage.removeItem('shiwen-selected');
  const url = new URL(location.href);url.searchParams.delete('task');history.replaceState(null,'',url);
  renderTask(null); renderHistory(); $('shareInput').value = ''; $('shareInput').focus();
  $('sidebar').classList.remove('open'); $('menuButton').setAttribute('aria-expanded', 'false');
});
$('search').addEventListener('input',renderHistory);
$('fontButton').addEventListener('click', () => {
  const sans = $('transcript').classList.toggle('sans'); $('fontButton').setAttribute('aria-pressed',String(sans));
  localStorage.setItem('shiwen-sans',String(sans));
});
$('copyButton').addEventListener('click', async () => {
  const text = state.current?.result?.text || state.current?.partial_text;
  if (!text) return;
  try {await navigator.clipboard.writeText(text);toast('全文已复制。');}
  catch {toast('浏览器未允许复制，请在正文中选择文字后复制。');}
});
$('exportMenu').addEventListener('click', event => {
  if (state.current?.status !== 'completed') {event.preventDefault();toast('完整文稿生成后即可下载。');return;}
  const kind = event.target.dataset.export;
  if (kind) {const a = document.createElement('a');a.href = `/api/tasks/${state.current.id}/export/${kind}`;a.download = '';a.click();$('exportMenu').open = false;}
});
$('retryButton').addEventListener('click', async () => {
  if (!state.selected) return;
  $('retryButton').disabled = true;
  try {await api(`/api/tasks/${state.selected}/retry`,{method:'POST'});await refresh();toast('已重新排队，会复用已完成的片段。');}
  catch(error){toast(error.message);}finally{$('retryButton').disabled = false;}
});
$('menuButton').addEventListener('click', () => {
  const expanded = $('sidebar').classList.toggle('open'); $('menuButton').setAttribute('aria-expanded',String(expanded));
});
document.addEventListener('keydown',event => {
  if (event.key === 'Escape') {$('sidebar').classList.remove('open');$('menuButton').setAttribute('aria-expanded','false');}
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && document.activeElement === $('shareInput')) $('captureForm').requestSubmit();
});
document.addEventListener('click', event => {
  if (!$('exportMenu').contains(event.target)) $('exportMenu').open = false;
  if (!$('sidebar').contains(event.target) && !$('menuButton').contains(event.target)) {$('sidebar').classList.remove('open');$('menuButton').setAttribute('aria-expanded','false');}
});
$('settingsButton').addEventListener('click', async () => {
  try {
    const config = await api('/api/settings');
    document.querySelector(`input[name="provider"][value="${config.provider}"]`).checked = true;
    $('keyStatus').textContent = config.key_configured ? '已配置，留空不修改' : '未配置';
    $('apiKey').value = ''; $('settingsMessage').textContent = '';
    $('settingsDialog').showModal();
  } catch(error) {toast(error.message);}
});
$('closeSettings').addEventListener('click', () => $('settingsDialog').close());
$('settingsForm').addEventListener('submit', async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try {
    const provider = document.querySelector('input[name="provider"]:checked').value;
    const config = await api('/api/settings',{method:'POST',body:JSON.stringify({provider,api_key:$('apiKey').value || null})});
    state.provider = config.provider; updateProvider(); $('apiKey').value = ''; $('settingsDialog').close();toast('设置已保存。');
  } catch(error) {$('settingsMessage').textContent = error.message;}
  finally {button.disabled = false;}
});
$('loginButton').addEventListener('click',async () => {
  $('loginButton').disabled = true;
  try {
    await api('/api/login',{method:'POST'});
    $('settingsMessage').textContent = '已打开独立的抖音浏览器。若需要，请扫码登录；登录后关闭整个窗口，再回到这里提取。';
  } catch(error) {$('settingsMessage').textContent = error.message;}
  finally {$('loginButton').disabled = false;}
});
function updateProvider() {
  $('engineBadge').replaceChildren(document.createElement('span'), document.createTextNode(state.provider === 'cloud' ? '云端识别' : '本地识别'));
}

async function boot() {
  document.querySelectorAll('svg').forEach(svg => svg.setAttribute('aria-hidden','true'));
  if (localStorage.getItem('shiwen-sans') === 'true') {$('transcript').classList.add('sans');$('fontButton').setAttribute('aria-pressed','true');}
  try {
    const config = await api('/api/settings');state.provider = config.provider;updateProvider();
    state.tasks = await api('/api/tasks');renderHistory();
    const previous = new URL(location.href).searchParams.get('task') || localStorage.getItem('shiwen-selected');
    if (previous && state.tasks.some(task => task.id === previous)) await selectTask(previous);
    else if (state.tasks.length) await selectTask(state.tasks[0].id);
  } catch(error) {toast(error.message);}
  setInterval(() => {if (!document.hidden) refresh();},2500);
  setInterval(renderElapsed,1000);
}
boot();

function renderBatch(task) {
  $('batchTitle').textContent = task.title;
  $('batchScope').textContent = `本批范围：${(task.max_duration_sec || 600)/60} 分钟以内 · 最多 ${task.limit} 条 · ${task.keep_media ? '保留原视频' : '成功后仅留文稿'}。`;
  $('batchStatus').textContent = (task.paused ? '已暂停排队，正在处理的一条会先完成。' : task.error || task.message) || '';
  const c = task.counts || {};
  $('batchCounts').textContent = `已发现 ${task.discovered || 0} 条 · 本批 ${(task.children || []).length} 条 · 成功 ${c.completed || 0} · 失败 ${c.failed || 0} · 跳过 ${Object.values(task.skipped || {}).reduce((a,b)=>a+b,0)+(c.skipped || 0)} · 待处理 ${(c.queued || 0)+(c.paused || 0)} · 正在处理 ${c.running || 0}`;
  const active = ['queued','running','processing'].includes(task.status);
  $('batchPause').disabled = !active || task.paused;
  $('batchResume').disabled = !task.paused;
  $('batchRetry').disabled = active;
  $('batchMore').disabled = active || !task.has_more || task.limit >= 10000;
  $('batchExport').href = `/api/batches/${task.id}/export`;
  if (!$('batchItems').contains(document.activeElement)) {
    const items = (task.items || []).map(item => {
      const li = document.createElement('li'); const button = document.createElement('button');
      button.className = 'text-button'; button.textContent = `${statusNames[item.status] || item.status} · ${item.title || item.video_id}`;
      button.addEventListener('click',()=>selectTask(item.id)); li.append(button);return li;
    });
    $('batchItems').replaceChildren(...items);
  }
}
$('captureMode').addEventListener('change',()=>{
  const batch = $('captureMode').value === 'batch';
  $('batchSettings').hidden = !batch;
  updateDurationHint();
  $('submitButton').firstChild.textContent = batch ? '开始批量提取' : '提取全文';
});
$('backBatch').addEventListener('click',()=>{if(state.current?.parent_id)selectTask(state.current.parent_id);});
for (const [id,action] of [['batchPause','pause'],['batchResume','resume'],['batchRetry','retry'],['batchMore','more']]) {
  $(id).addEventListener('click',async()=>{
    $(id).disabled=true;
    try {await api(`/api/batches/${state.selected}/${action}`,{method:'POST'});await refresh();}
    catch(error){toast(error.message);}finally{if(state.current?.kind==='creator')renderBatch(state.current);}
  });
}

function updateDurationHint() {
  const minutes = Number(document.querySelector('input[name="maxDuration"]:checked').value)/60;
  $('durationHint').textContent = `仅提取 ${minutes} 分钟以内的视频，超长作品自动跳过。${minutes > 10 ? '视频越长，下载和识别用时也会增加。' : ''}`;
  $('inputHint').textContent = $('captureMode').value === 'batch' ? `主页或任意作品链接 · ${minutes}分钟以内 · 待确认素材保留` : '中文口播优先 · 建议10分钟以内';
}
document.querySelectorAll('input[name="maxDuration"]').forEach(input=>input.addEventListener('change',updateDurationHint));

$('newTask').addEventListener('click',()=>{
  document.querySelector('input[name="maxDuration"][value="600"]').checked = true;
  $('batchLimit').value = '10'; $('keepMedia').checked = false;
  updateDurationHint();
});
