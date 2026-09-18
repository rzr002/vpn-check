'use strict';
const $ = id => document.getElementById(id);
const hosts = ['百度', 'Cloudflare', 'Google', 'GitHub'];
const domains = {'百度':'www.baidu.com', Cloudflare:'speed.cloudflare.com', Google:'www.google.com', GitHub:'github.com'};
let current = {status:'idle', data:null};
let historical = null;
let selectedReport = null;
let token = '';
let online = false;
let pending = false;
let previousStatus = '';
let previousRun = null;

async function api(path, body) {
  const options = {signal:AbortSignal.timeout(path === '/api/network' ? 30000 : 10000)};
  if (body !== undefined) Object.assign(options, {method:'POST', headers:{'Content-Type':'application/json','X-VPN-Token':token}, body:JSON.stringify(body)});
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '本地服务暂时不可用');
  return result;
}
function sayError(message) { $('service-error').textContent=message; $('service-error').hidden=!message; }
function isGood(row) { return row && row.exit_code === 0 && row.status >= 200 && row.status < 400; }
function median(values) { if (!values.length) return null; const s=[...values].sort((a,b)=>a-b), m=Math.floor(s.length/2); return s.length%2?s[m]:(s[m-1]+s[m])/2; }
function average(values) { return values.length ? values.reduce((a,b)=>a+b,0)/values.length : null; }
function number(value, digits=0) { return value == null || !Number.isFinite(value) ? '—' : value.toFixed(digits); }
function stats(rows=[]) { return {n:rows.length, good:rows.filter(isGood).length, median:median(rows.filter(isGood).map(r=>r.ttfb_ms)),
  variation:average(rows.slice(1).map((r,i)=>isGood(r)&&isGood(rows[i])?Math.abs(r.ttfb_ms-rows[i].ttfb_ms):null).filter(v=>v!==null)),
  transport:rows.filter(r=>r.exit_code!==0 || !r.status).length, rejected:rows.filter(r=>r.exit_code===0 && r.status>=400).length}; }
function formatDate(value) { const date=new Date(value); return Number.isNaN(date.valueOf())?'时间未知':date.toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}); }
function duration(seconds) { const s=Math.max(0,Math.floor(seconds||0)); return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`; }
function node(tag, text, className) { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(className)n.className=className; return n; }
function data() { return selectedReport ? historical : current.data; }
function active() { return ['running','stopping'].includes(current.status); }

function renderControls() {
  $('start').disabled = !online || !token || active() || pending || !!current.demo;
  $('start-label').textContent = current.demo ? '演示预览 · 不执行检测' : !online ? '等待本地服务' : active() ? '检测进行中' : current.status==='idle' ? '开始检测' : '重新检测';
  $('mode-options').disabled = active() || pending || !!current.demo;
  $('demo-banner').hidden = !current.demo;
  $('stop').hidden = !active();
  $('stop').disabled = current.status==='stopping' || pending || !online;
  $('run-message').textContent = current.message || '准备就绪';
  $('percent').textContent = `${Math.round(current.progress || 0)}%`;
  $('progress').value = current.progress || 0;
  $('run-phase').textContent = current.status==='complete' ? '报告已保存' : current.status==='cancelled' ? '部分数据' : current.status==='failed' ? '可重试' : '随时可以停止';
  const elapsed = active() && current.started_at ? (Date.now()-new Date(current.started_at))/1000 : current.data?.elapsed_seconds;
  $('elapsed').textContent = current.status==='idle' ? '尚未开始' : `已用时 ${duration(elapsed)}`;
  $('back-current').hidden = !selectedReport;
}

function render() {
  renderControls();
  const d=data(), historicalView=!!selectedReport;
  $('view-kind').textContent = historicalView ? 'SAVED MEASUREMENT' : 'LIVE DIAGNOSTICS';
  const titles = {idle:'等待开始检测',running:'正在观察你的网络',stopping:'正在停止检测',complete:'检测完成',cancelled:'检测已停止',failed:'检测未完成'};
  const badges = {idle:'准备就绪',running:'实时采样',stopping:'正在停止',complete:'已完成',cancelled:'部分结果',failed:'请检查连接'};
  $('result-title').textContent = historicalView ? '历史检测结果' : titles[current.status] || '检测结果';
  $('result-subtitle').textContent = d ? `${formatDate(d.started)} · ${d.proxy || '代理未知'}${historicalView ? ' · 历史数据' : ''}` : '先运行快速诊断；间歇卡顿再选稳定性观察。';
  $('view-badge').textContent = historicalView ? '历史记录' : badges[current.status] || '未知';
  $('view-badge').className = `status-pill ${historicalView?'':current.status}`;
  if (current.demo) {
    $('result-title').textContent = '一份检测报告，能看到什么';
    $('view-kind').textContent = 'SYNTHETIC DEMO';
    $('view-badge').textContent = '合成演示';
    $('run-phase').textContent = '未发起网络请求';
    $('result-subtitle').textContent = '用示例了解速度、响应与路径对照 · 非实测结果';
    $('traffic-note').textContent = '合成数据预览 · 不消耗测速流量';
  }
  const proxyRows = Object.entries(d?.probes||{}).filter(([key])=>key.endsWith('/ 经代理')).flatMap(([,rows])=>rows);
  const allStats=stats(proxyRows), google=stats(d?.probes?.['Google / 经代理']);
  const downloadRows=(d?.downloads||[]).filter(r=>r.path==='经代理');
  const speeds=downloadRows.map(r=>r.mbps).filter(v=>Number.isFinite(v));
  $('speed-value').textContent=number(average(speeds),1);
  $('speed-detail').textContent=speeds.length ? `${speeds.length} 次有效下载 · 约 ${number(average(speeds)/8,1)} MB/s` : downloadRows.length ? '下载未完整成功' : (historicalView || current.status==='complete') && d ? '本轮未执行下载' : current.mode==='stability' && !historicalView ? '稳定性模式不进行下载' : !historicalView && ['cancelled','failed'].includes(current.status) ? '本轮未完成下载' : '等待定量下载';
  $('response-value').textContent=number(google.median);
  $('response-detail').textContent=google.n ? `经代理 · ${google.good}/${google.n} 成功 · 取中位数` : '经代理 · 成功样本中位数';
  $('success-value').textContent=allStats.n?number(allStats.good/allStats.n*100,1):'—';
  $('success-detail').textContent=allStats.n ? `${allStats.good}/${allStats.n} 成功 · ${allStats.transport} 传输失败 · ${allStats.rejected} HTTP 拒绝` : '等待网页响应';
  $('loss-value').textContent=number(d?.gateway_ping?.loss_percent,1);
  $('loss-detail').textContent=d?.gateway_ping?.available ? `本地网关平均 ${number(d.gateway_ping.rtt_min_avg_max_stddev_ms?.[1],1)} ms` : d?.gateway_ping ? '未测得 · 网关可能不响应 ICMP' : '20 个 ICMP 样本 · 非节点丢包';
  renderInsight(d);
  renderChart(d);
  renderTable(d);
  $('sample-note').textContent = d ? (historicalView||current.status==='complete' ? `覆盖 ${duration(d.elapsed_seconds)} · 只反映采样窗口，不代表长期稳定。` : current.status==='cancelled' ? '已停止：以上仅为部分样本，未生成完整报告。' : '本轮样本正在累积，测试结束后自动保存。') : '完成后自动保存本地报告。';
  $('export').disabled=!d;
}

function renderInsight(d) {
  const direct=stats(d?.probes?.['百度 / 绕过代理']), proxy=stats(d?.probes?.['百度 / 经代理']);
  let text='';
  if (direct.median>0 && proxy.median/direct.median>2 && d?.before?.clash?.mode==='global') text=`本轮百度经代理响应约为绕过代理的 ${(proxy.median/direct.median).toFixed(1)} 倍。测试时为 Global 模式，全局代理增加的等待值得优先排查。`;
  else if (d?.before?.clash?.tun===true) text='测试时 TUN 已开启：“绕过代理”的请求仍可能被隧道接管，请结合观测节点理解两条路径。';
  $('insight').textContent=text; $('insight').hidden=!text;
}

function renderTable(d) {
  const body=$('comparison');body.replaceChildren();
  for(const host of hosts) {
    const row=node('tr');row.append(node('td',host));
    for(const path of ['绕过代理','经代理']) {
      const s=stats(d?.probes?.[`${host} / ${path}`]);
      const cell=node('td',s.median!==null?`${number(s.median)} ms`:s.n?'未成功':'—',s.n&&!s.good?'failed':'');
      if(s.n)cell.append(node('small',`${s.good}/${s.n}`));
      cell.title=`${s.n} 个样本，${s.transport} 次传输失败，${s.rejected} 次 HTTP 拒绝`;
      row.append(cell);
    }
    row.append(node('td',`${number(stats(d?.probes?.[`${host} / 经代理`]).variation)}${stats(d?.probes?.[`${host} / 经代理`]).variation!==null?' ms':''}`));
    const chains=[...new Set((d?.paths||[]).filter(p=>p.host===domains[host]).map(p=>p.chains?.[0]).filter(Boolean))];
    const chain=node('td',chains.length?chains.join(' / '):'未捕获');chain.title=chains.join(' / ')||'活跃连接采样中尚未捕获此域名';row.append(chain);body.append(row);
  }
}

function renderChart(d) {
  const svg=$('chart');svg.replaceChildren();
  function item(tag,attrs,text) { const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,v] of Object.entries(attrs))el.setAttribute(key,String(v));if(text!==undefined)el.textContent=text;svg.append(el);return el; }
  const host=$('chart-host').value;
  const sets=[{rows:d?.probes?.[`${host} / 经代理`]||[],kind:'proxy'}, {rows:d?.probes?.[`${host} / 绕过代理`]||[],kind:'direct'}];
  const count=Math.max(...sets.map(s=>s.rows.length),0);
  const max=Math.max(400,...sets.flatMap(s=>s.rows.filter(isGood).map(r=>r.ttfb_ms)));
  const ceiling=Math.ceil(max/200)*200;
  for(let i=0;i<=3;i++){const y=15+i*43;item('line',{x1:42,y1:y,x2:748,y2:y,class:'chart-grid'});item('text',{x:0,y:y+4,class:'chart-label'},number(ceiling*(1-i/3)));}
  $('chart-empty').hidden=count>0;
  svg.setAttribute('aria-label',count?`${host} 的 ${count} 轮首字节响应曲线，单位毫秒`:'尚无响应数据');
  if(!count)return;
  const x=i=>count===1?42:42+i/(count-1)*706, y=t=>144-t/ceiling*129;
  for(const {rows,kind} of sets){
    let path='',connected=false;
    rows.forEach((r,i)=>{if(isGood(r)){path+=`${connected?'L':'M'}${x(i).toFixed(2)},${y(r.ttfb_ms).toFixed(2)} `;connected=true;const point=item('circle',{cx:x(i),cy:y(r.ttfb_ms),r:2.5,class:`chart-point-${kind}`});const title=document.createElementNS(svg.namespaceURI,'title');title.textContent=`第 ${i+1} 轮：${number(r.ttfb_ms)} ms`;point.append(title);}else{connected=false;const fy=kind==='proxy'?156:168;item('path',{d:`M${x(i)-3},${fy-3}l6,6m0,-6l-6,6`,class:`chart-path-${kind}`});}});
    item('path',{d:path,class:`chart-path-${kind}`});
  }
  item('text',{x:42,y:188,class:'chart-label'},'第 1 轮');
  if(count>1)item('text',{x:747,y:188,class:'chart-label','text-anchor':'end'},`第 ${count} 轮`);
}

async function refreshNetwork() {
  $('refresh-network').disabled=true;
  try {
    const n=await api('/api/network');
    const c=n.clash||{};
    $('connection-title').textContent=current.demo?'Clash 状态示例（演示）':c.available?'Clash 控制器可用':'未检测到 Clash';
    $('connection-dot').className=`dot ${c.available?'':'warning'}`;
    $('proxy-port').textContent=c.port?`127.0.0.1:${c.port}`:'未检测到';
    $('proxy-mode').textContent={global:'Global · 全局',rule:'Rule · 分流',direct:'Direct · 直连'}[c.mode]||'未知';
    $('tun').textContent=c.tun===true?'已开启':c.tun===false?'已关闭':'未知';
    $('cisco').textContent=n.cisco?.at(-1)||'未知';
    $('network-time').textContent=`状态采集于 ${formatDate(n.at)} · 非连通性结论`;
  } catch { $('connection-title').textContent='连接状态未能读取';$('connection-dot').className='dot warning';$('network-time').textContent='请确认本地服务仍在运行，再刷新。'; }
  finally{$('refresh-network').disabled=false;}
}

async function refreshHistory() {
  try {
    const rows=await api('/api/history');
    $('history-count').textContent=`${rows.length} 次已保存`;
    const list=$('history-list');list.replaceChildren();
    if(!rows.length){list.append(node('p',current.demo?'演示模式不读取或保存本地检测记录。':'还没有检测记录。完成第一轮后会自动保存在这里。','small-muted'));return;}
    for(const r of rows){const button=node('button',undefined,`history-item ${selectedReport===r.id?'active':''}`);button.dataset.report=r.id;
      button.append(node('strong',formatDate(r.started)));const info=node('small');info.append(node('span',r.downloads?'快速诊断 · 含下载':'稳定性记录'),node('span',`${duration(r.elapsed_seconds)} ↗`));button.append(info);
      button.addEventListener('click',async()=>{try{const report=await api('/api/reports/'+encodeURIComponent(r.id));selectedReport=r.id;historical=report;render();markHistory();}catch(e){sayError(e.message);}});list.append(button);}
  }catch{$('history-count').textContent='读取失败';$('history-list').replaceChildren(node('p','无法读取历史记录，请确认本地服务已启动。','small-muted'));}
}
function markHistory(){for(const el of document.querySelectorAll('.history-item'))el.classList.toggle('active',el.dataset.report===selectedReport);}

async function poll() {
  try {
    const next=await api('/api/state');
    token=next.token;online=true;current=next;sayError('');
    if(next.id!==previousRun && next.status==='running'){selectedReport=null;historical=null;markHistory();}
    if(next.status!==previousStatus && ['complete','cancelled','failed'].includes(next.status)){refreshHistory();refreshNetwork();}
    previousRun=next.id;previousStatus=next.status;
    render();
  }catch{online=false;renderControls();sayError('本地服务连接中断。请双击「打开检测面板.command」启动服务；页面会自动重连。');}
  finally{setTimeout(poll,1200);}
}
$('start').addEventListener('click',async()=>{
  pending=true;renderControls();
  try{current=await api('/api/start',{mode:document.querySelector('input[name="mode"]:checked').value});selectedReport=null;historical=null;previousRun=current.id;previousStatus=current.status;sayError('');markHistory();render();}
  catch(e){sayError(e.message);}
  finally{pending=false;renderControls();}
});
$('stop').addEventListener('click',async()=>{pending=true;renderControls();try{current=await api('/api/stop',{});render();}catch(e){sayError(e.message);}finally{pending=false;renderControls();}});
$('back-current').addEventListener('click',()=>{selectedReport=null;historical=null;render();markHistory();});
$('refresh-network').addEventListener('click',refreshNetwork);
$('chart-host').addEventListener('change',()=>renderChart(data()));
for(const radio of document.querySelectorAll('input[name="mode"]'))radio.addEventListener('change',()=>{$('traffic-note').textContent=radio.value==='stability'?'60 轮持续采样 · 不执行下载测速 · 慢请求可能延长时间':'本轮下载约 40 MiB · 4 个网站 · 双路径对照';});
$('export').addEventListener('click',()=>{const d=data();if(!d)return;const blob=new Blob([JSON.stringify(d,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=node('a');link.href=url;link.download=`vpn-check-${selectedReport||current.report_id||'partial'}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
render();poll();refreshHistory();refreshNetwork();
