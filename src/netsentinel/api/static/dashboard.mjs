import {Api, ApiError, EventFeed, eventNames, graphData, riskStyle, counterInterval} from './core.mjs';

const $ = id => document.getElementById(id);
const api = new Api();
const labels = {risk_evaluated: 'Risco avaliado', mitigation_applied: 'Mitigação aplicada',
  mitigation_status: 'Estado da mitigação', mitigation_error: 'Falha na mitigação',
  reputation_changed: 'Reputação alterada', baseline_calibrated: 'Baseline calibrado',
  snapshot_updated: 'Captura atualizada', source_error: 'Fonte interrompida',
  threat_unmitigable: 'Ameaça sem mitigação autorizada'};
const reputations = {known: 'Reconhecido', new: 'Novo', unknown: 'Sem informação'};
const actions = {confirm: 'Dispositivo confirmado', revoke: 'Reconhecimento revogado', bootstrap: 'Inventário importado',
  calibration_started: 'Calibração iniciada', calibration_completed: 'Calibração concluída'};
let epoch = 0, signedIn = false, socket = null, syncJob = null, dirty = false, refreshTimer;
let devices = [], status = null, topology = {nodes: [], links: []}, selected = null;
let evidenceEvents = [], lastMitigationError = 0, snapshot = null, snapshotID = 0;
let graph, graphNodes, graphEdges, fitted = false, detailRequest = 0, calibration = null;
const feed = new EventFeed(acceptEvent);
const fmt = value => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('pt-BR', {maximumFractionDigits: 2}) : '—';
const when = value => typeof value === 'number' ? new Date(value * 1000).toLocaleString('pt-BR') : '—';
const node = (tag, text, cls) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; };
function badge(text, cls = '') { return node('span', text, `badge ${cls}`); }
function message(text, id = 'feedback') { $(id).textContent = text; $(id).hidden = !text; }
function errorText(error) {
  const known = {invalid_credentials: 'Usuário ou senha incorretos.', csrf_required: 'A sessão de segurança mudou. Atualize a página e tente novamente.',
    repository_unavailable: 'Banco indisponível. Os dados exibidos podem estar desatualizados.',
    authentication_required: 'Sessão encerrada. Entre novamente.'};
  if (error instanceof ApiError) return known[error.message] || error.message;
  return 'Não foi possível comunicar com o backend. Verifique a conexão e tente novamente.';
}
function fail(error, id = 'feedback') {
  if (error.status === 401 && signedIn) { endSession('Sessão encerrada. Entre novamente.'); return; }
  message(errorText(error), id);
}
function endSession(text = '') {
  epoch++; signedIn = false; api.csrf = null;
  clearTimeout(refreshTimer); socket?.disconnect(); socket = null;
  feed.reset(); devices = []; status = null; evidenceEvents = []; lastMitigationError = 0;
  snapshot = null; snapshotID = 0; selected = null; calibration = null; detailRequest++;
  graph?.destroy(); graph = null; fitted = false;
  $('device-dialog').close(); $('workspace').hidden = true; $('login-panel').hidden = false;
  for (const id of ['devices', 'events', 'audit', 'detail-data']) $(id).replaceChildren();
  $('mode').textContent = 'Ambiente não consultado'; $('password').value = '';
  message(text, 'login-message');
}
async function startSession(info) {
  const version = ++epoch; signedIn = true;
  $('operator').textContent = info.operator; $('login-panel').hidden = true; $('workspace').hidden = false;
  $('mode').textContent = info.mode === 'cloud' ? 'NUVEM · DADOS SINTÉTICOS' : 'LABORATÓRIO · REDE ISOLADA';
  message('');
  if (!window.io || !window.vis) { message('Arquivos locais da interface não carregaram. Recarregue a página.'); return; }
  createGraph();
  socket = window.io({autoConnect: false, transports: ['websocket'], auth: {csrf_token: api.csrf}});
  socket.on('connect', () => { if (version !== epoch) return; $('connection').textContent = 'Eventos conectados'; scheduleRefresh(); });
  socket.on('disconnect', reason => {
    if (version !== epoch || !signedIn) return;
    $('connection').textContent = 'Eventos desconectados · dados podem estar antigos';
    // Logout/expiração no servidor desconecta sem reconexão automática.
    if (reason === 'io server disconnect') {
      api.request('/api/auth/session').then(() => { if (version === epoch) socket?.connect(); }).catch(e => fail(e));
    }
  });
  socket.on('connect_error', () => {
    if (version !== epoch) return;
    $('connection').textContent = 'Falha na conexão de eventos';
    // Detectar expiração; não mascarar falha como atualização em tempo real.
    api.request('/api/auth/session').catch(e => { if (version === epoch) fail(e); });
  });
  for (const name of eventNames) socket.on(name, event => {
    if (version !== epoch) return;
    feed.ingest(event); renderEvents(); renderEvidence(); renderStatus(); scheduleRefresh();
  });
  socket.connect();
  await synchronize();
}
function acceptEvent(event) {
  if (event.event === 'snapshot_updated' && event.event_id > snapshotID) {
    snapshotID = event.event_id; snapshot = event.snapshot;
  }
  if (event.event === 'mitigation_error') lastMitigationError = Math.max(lastMitigationError, event.event_id);
  if (['mitigation_applied', 'mitigation_status'].includes(event.event) && event.evidence) {
    evidenceEvents = [...evidenceEvents.filter(e => e.event_id !== event.event_id), event]
      .sort((a,b) => a.event_id - b.event_id).slice(-2);
  }
}
function scheduleRefresh() {
  if (!signedIn) return;
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => synchronize(), 200);
}
async function synchronize() {
  if (!signedIn) return;
  if (syncJob) { dirty = true; return syncJob; }
  const version = epoch;
  syncJob = (async () => {
    $('refresh').disabled = true;
    try {
      await feed.replay(api, () => signedIn && epoch === version);
      if (epoch !== version) return;
      const values = await Promise.all(['/api/topology', '/api/devices', '/api/audit', '/api/status'].map(p => api.request(p)));
      if (epoch !== version) return;
      [topology, {devices}, , status] = values;
      updateGraph(); renderDevices(); renderEvents(); renderAudit(values[2].audit); renderStatus(); renderEvidence();
      message('');
      if ($('device-dialog').open) await loadDetails();
    } catch (error) { if (epoch === version) fail(error); }
    finally {
      syncJob = null; $('refresh').disabled = false;
      if (dirty && signedIn) { dirty = false; scheduleRefresh(); }
    }
  })();
  return syncJob;
}
function createGraph() {
  graphNodes = new window.vis.DataSet(); graphEdges = new window.vis.DataSet();
  graph = new window.vis.Network($('network'), {nodes: graphNodes, edges: graphEdges}, {
    locale: 'pt-br', layout: {randomSeed: 42}, physics: {stabilization: {iterations: 100}},
    interaction: {hover: true, keyboard: {enabled: true, bindToWindow: false}},
    edges: {width: 1.5}, nodes: {chosen: true}, manipulation: false
  });
  graph.on('selectNode', ({nodes}) => { if (devices.some(d => d.mac === nodes[0])) openDetails(nodes[0]); });
  graph.on('stabilizationIterationsDone', () => graph?.setOptions({physics: false}));
}
function reconcile(dataset, incoming) {
  const ids = new Set(incoming.map(item => item.id));
  dataset.remove(dataset.getIds().filter(id => !ids.has(id)));
  dataset.update(incoming);
}
function updateGraph() {
  if (!graph) return;
  const data = graphData(topology);
  const structureChanged = data.nodes.some(n => !graphNodes.get(n.id));
  reconcile(graphNodes, data.nodes); reconcile(graphEdges, data.edges);
  $('graph-empty').hidden = data.nodes.length > 0;
  if (structureChanged) graph.setOptions({physics: {enabled: true}});
  if (!fitted && data.nodes.length) { fitted = true; graph.fit({animation: false}); }
}
function renderStatus() {
  if (!status) return;
  $('mode').textContent = status.mode === 'cloud' ? 'NUVEM · DADOS SINTÉTICOS' : 'LABORATÓRIO · REDE ISOLADA';
  $('source-state').textContent = status.source_running ? 'Fonte em execução' : 'Fonte parada';
  $('window').textContent = `${status.window_seconds} s`;
  const ts = status.last_snapshot_at;
  $('last-snapshot').textContent = when(ts);
  let warning = status.source_error ? 'A fonte parou por erro. Consulte os registros do backend antes de reiniciar.' :
    !status.source_running ? 'A fonte não está em execução. Os dados exibidos são históricos.' :
    !ts ? 'Aguardando a primeira captura.' :
    Date.now()/1000 - ts > status.window_seconds * 2 ? 'Captura sem atualização recente. Não trate estes dados como atuais.' :
    snapshot?.incomplete ? 'Janela incompleta: houve perda de observações. Aguarde uma janela íntegra.' :
    snapshot?.warming_up ? 'Captura em aquecimento: aguardando completar a janela de 8 segundos.' : '';
  // Apenas a apresentação do frescor usa relógio. Não há polling periódico de dados.
  message(warning, 'source-warning');
}
function renderDevices() {
  const rows = devices.map(d => {
    const tr = node('tr'); tr.append(node('td', d.mac, 'mono'), node('td', reputations[d.reputation] || 'Sem informação'));
    const risk = node('td'), style = riskStyle(d.risk);
    risk.append(node('span', fmt(d.risk?.score), 'score'), badge(style.label, style.css));
    tr.append(risk, node('td', d.baseline_bps === null ? 'Indisponível' : `${fmt(d.baseline_bps)} bytes/s`), node('td', when(d.last_seen)));
    const action = node('td'), button = node('button', 'Detalhes'); button.type = 'button';
    button.setAttribute('aria-label', `Detalhes de ${d.mac}`); button.addEventListener('click', () => openDetails(d.mac));
    action.append(button); tr.append(action); return tr;
  });
  $('devices').replaceChildren(...rows); $('devices-empty').hidden = rows.length > 0;
  $('device-count').textContent = `(${rows.length})`;
}
function renderEvents() {
  const events = feed.newest();
  $('history-note').textContent = `Até 200 eventos mais recentes · ordem do registro, mais novo primeiro · cursor recuperado: ${feed.cursor}`;
  const expanded = new Set([...$('events').querySelectorAll('details[open]')].map(el => el.dataset.id));
  $('events').replaceChildren(...events.map(e => {
    const li = node('li'); const time = node('time', when(e.timestamp)); time.dateTime = new Date(e.timestamp*1000).toISOString();
    const detail = node('details'), summary = node('summary', labels[e.event] || e.event);
    summary.append(document.createTextNode(' '), badge(e.source === 'synthetic' ? 'Sintético' : 'Laboratório', e.event.includes('error') ? 'danger' : ''));
    detail.dataset.id = String(e.event_id);
    detail.append(summary);
    const populate = () => { if (detail.open && !detail.querySelector('pre')) detail.append(node('pre', JSON.stringify(e, null, 2))); };
    detail.addEventListener('toggle', populate);
    if (expanded.has(detail.dataset.id)) { detail.open = true; populate(); }
    li.append(time, detail); return li;
  }));
  $('events-empty').hidden = events.length > 0;
}
function renderAudit(audits) {
  $('audit').replaceChildren(...audits.map(a => {
    const li = node('li'), content = node('div');
    content.append(node('strong', actions[a.action] || a.action), node('p', `${a.mac} · ${a.actor}`, 'mono'), node('p', a.reason));
    li.append(node('time', when(a.timestamp)), content); return li;
  }));
  $('audit-empty').hidden = audits.length > 0;
}
function renderEvidence() {
  const afterEvent = evidenceEvents.at(-1), after = afterEvent?.evidence, before = evidenceEvents.at(-2)?.evidence;
  const error = lastMitigationError > (afterEvent?.event_id || 0);
  $('mitigation-state').textContent = error ? 'Falha ao consultar ou aplicar defesa' : !after ? 'Aguardando evidências' :
    after.mitigated ? 'Mitigação reportada pelo agente' : 'Mitigação não confirmada';
  $('mitigation-state').className = `evidence-state ${error ? 'text-red-300' : ''}`;
  $('target-mac').textContent = after?.attacker_mac || '—';
  $('arp-state').textContent = after ? (after.arp_static_correct === true ? 'Confirmado na leitura' : 'Não confirmado') : 'Não verificado';
  $('block-state').textContent = after ? (after.blocked === true ? 'Confirmada na leitura' : 'Não confirmada') : 'Não verificada';
  $('evidence-origin').textContent = after ? `${after.simulated || afterEvent.source === 'synthetic' ? 'SIMULAÇÃO · não comprova defesa real' : 'Agente da Vítima'} · última leitura ${when(after.timestamp)}` : 'Nenhuma leitura do agente disponível.';
  const interval = counterInterval(before, after);
  $('counters').replaceChildren(...[['seen','Vistos'], ['dropped','Descartados'], ['passed','Entregues']].map(([key, label]) => {
    const row = node('tr'); row.append(...[label, fmt(before?.counters?.[key]?.packets), fmt(after?.counters?.[key]?.packets), fmt(interval.deltas?.[key])].map(x => node('td', x))); return row;
  }));
  $('interval-state').textContent = `${before && after ? `${when(before.timestamp)} → ${when(after.timestamp)}. ` : ''}${interval.reason}${error ? ' Últimas leituras são históricas; há falha posterior.' : ''}`;
}
async function openDetails(mac) {
  selected = mac; calibration = null; $('reputation-reason').value = ''; message('', 'detail-message');
  $('detail-title').textContent = mac; $('device-dialog').showModal();
  await loadDetails();
}
async function loadDetails() {
  const requestID = ++detailRequest, version = epoch, mac = selected;
  renderDetails(); $('calibrate').disabled = true;
  try {
    const data = await api.request(`/api/devices/${encodeURIComponent(mac)}/calibrations`);
    if (requestID !== detailRequest || epoch !== version || selected !== mac) return;
    calibration = data.calibrations[0] || null; renderDetails();
  } catch (error) { if (epoch === version && selected === mac) fail(error, 'detail-message'); }
}
function renderObserved(d) {
  const section = node('section', undefined, 'detail-section');
  section.append(node('h3', 'Evidência observada'));
  section.append(node('p', 'Não entra na inferência fuzzy.', 'muted'));
  const observed = snapshot?.devices?.[d.mac] || {};
  const protocols = Object.entries(observed.protocols || {})
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([name, count]) => `${name} ${fmt(count)}`)
    .join(', ') || '—';
  const ips = Array.isArray(observed.claimed_ips) ? observed.claimed_ips : [];
  const total = Number.isFinite(observed.claimed_ips_total) ? observed.claimed_ips_total : ips.length;
  let ipText = ips.join(', ') || '—';
  if (total > ips.length) ipText += ` (+${total - ips.length})`;
  const facts = node('dl', undefined, 'facts');
  const rows = [['Protocolos', protocols], ['IPs observados', ipText]];
  const ratio = d.risk?.inputs?.arp_reply_ratio;
  if (Number.isFinite(ratio)) rows.push(['Proporção de replies ARP', fmt(ratio)]);
  for (const [label, value] of rows) {
    const row = node('div'); row.append(node('dt', label), node('dd', value)); facts.append(row);
  }
  section.append(facts);
  return section;
}
function renderDetails() {
  const d = devices.find(d => d.mac === selected); if (!d) return;
  const entries = [['Reputação', reputations[d.reputation]], ['Risco', `${fmt(d.risk?.score)} · ${riskStyle(d.risk).label}`],
    ['Motivo do score nulo', d.risk?.reason || '—'], ['Conflito ARP', fmt(d.risk?.inputs?.conflict)],
    ['Frequência ARP', `${fmt(d.risk?.inputs?.arp_frequency)} /s`], ['Desvio de volume', fmt(d.risk?.inputs?.volume_deviation)],
    ['Baseline', d.baseline_bps == null ? 'Indisponível' : `${fmt(d.baseline_bps)} bytes/s`]];
  const dl = node('dl', undefined, 'facts');
  for (const [label, value] of entries) { const row = node('div'); row.append(node('dt', label), node('dd', value)); dl.append(row); }
  $('detail-data').replaceChildren(dl, renderObserved(d));
  $('reputation-help').textContent = d.reputation === 'known' ? 'Revogar retorna este MAC a Novo e cancela a calibração ativa.' : 'Confirme somente após reconhecer este dispositivo. Não há promoção automática por score.';
  $('reputation-submit').textContent = d.reputation === 'known' ? 'Revogar reconhecimento' : 'Confirmar dispositivo';
  const names = {collecting: 'Coletando', completed: 'Concluída', cancelled: 'Cancelada', interrupted: 'Interrompida'};
  $('calibration-state').textContent = calibration ? `${names[calibration.status] || calibration.status} · ${calibration.samples.length}/5 janelas aceitas` : 'Nenhuma calibração registrada.';
  $('calibrate').textContent = d.baseline_bps == null ? 'Iniciar calibração' : 'Recalibrar baseline';
  const blocked = d.reputation !== 'known'
    ? 'Confirme o dispositivo como conhecido antes de calibrar.'
    : calibration?.status === 'collecting'
      ? 'Calibração em coleta; aguarde as cinco janelas.'
      : !status?.source_running
        ? 'A fonte está parada; a calibração precisa de janelas novas.'
        : '';
  $('calibrate').disabled = Boolean(blocked);
  $('calibrate').title = blocked;
  const reason = $('calibrate-reason');
  reason.textContent = blocked;
  reason.hidden = !blocked;
}
$('login-form').addEventListener('submit', async event => {
  event.preventDefault(); $('login-button').disabled = true; message('Entrando…', 'login-message');
  try {
    await api.login($('username').value, $('password').value); $('password').value = '';
    const info = await api.request('/api/auth/session'); await startSession(info);
  } catch (error) { message(errorText(error), 'login-message'); }
  finally { $('login-button').disabled = false; }
});
$('logout').addEventListener('click', async () => {
  $('logout').disabled = true;
  try { await api.request('/api/auth/logout', 'POST'); endSession('Sessão encerrada.'); }
  catch (error) { fail(error); }
  finally { $('logout').disabled = false; }
});
$('refresh').addEventListener('click', async () => {
  const version = epoch;
  try {
    if (socket && !socket.connected) {
      await api.prepareCsrf();
      if (epoch !== version) return;
      socket.auth = {csrf_token: api.csrf}; socket.connect();
    }
    await synchronize();
  } catch (error) { if (epoch === version) fail(error); }
});
$('fit').addEventListener('click', () => graph?.fit({animation: false}));
$('close-detail').addEventListener('click', () => $('device-dialog').close());
$('device-dialog').addEventListener('close', () => { selected = null; detailRequest++; });
$('reputation-form').addEventListener('submit', async event => {
  event.preventDefault(); const d = devices.find(d => d.mac === selected); if (!d) return;
  const version = epoch, mac = selected; $('reputation-submit').disabled = true;
  try {
    await api.request(`/api/devices/${encodeURIComponent(mac)}/reputation`, 'POST', {known: d.reputation !== 'known', reason: $('reputation-reason').value});
    if (epoch !== version) return;
    message('Reputação atualizada e ação registrada na auditoria.', 'detail-message');
    $('reputation-reason').value = ''; await synchronize();
  } catch (error) { if (epoch === version) fail(error, 'detail-message'); }
  finally { $('reputation-submit').disabled = false; }
});
$('calibrate').addEventListener('click', async () => {
  const version = epoch, mac = selected; $('calibrate').disabled = true;
  try {
    await api.request(`/api/devices/${encodeURIComponent(mac)}/calibrations`, 'POST');
    if (epoch !== version) return;
    message('Calibração iniciada. Aguardando cinco janelas válidas.', 'detail-message');
    await synchronize();
  } catch (error) { if (epoch === version) { fail(error, 'detail-message'); renderDetails(); } }
});
for (const view of ['events', 'audit']) $(`show-${view}`).addEventListener('click', () => {
  for (const target of ['events', 'audit']) { $(`${target}-panel`).hidden = target !== view; $(`show-${target}`).setAttribute('aria-pressed', String(target === view)); }
});
// Este timer só envelhece o indicador visual; dados chegam por Observer/REST inicial.
setInterval(() => { if (signedIn) renderStatus(); }, 1000);
async function restore() {
  $('login-button').disabled = true;
  try { await api.prepareCsrf(); await startSession(await api.request('/api/auth/session')); }
  catch (error) { message(error.status === 401 ? '' : errorText(error), 'login-message'); }
  finally { $('login-button').disabled = false; }
}
restore();
