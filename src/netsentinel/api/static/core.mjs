/* Contratos puros: testáveis sem navegador, VM ou interface de captura. */
export const eventNames = ['risk_evaluated', 'mitigation_applied', 'mitigation_status',
  'mitigation_error', 'reputation_changed', 'baseline_calibrated', 'snapshot_updated', 'source_error'];

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
export class Api {
  constructor(fetcher = globalThis.fetch.bind(globalThis)) { this.fetcher = fetcher; this.csrf = null; }
  async request(path, method = 'GET', body) {
    const headers = {Accept: 'application/json'};
    if (method !== 'GET') headers['X-CSRF-Token'] = this.csrf || '';
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const response = await this.fetcher(path, {method, headers, credentials: 'same-origin',
      cache: 'no-store', signal: AbortSignal.timeout(10000),
      ...(body === undefined ? {} : {body: JSON.stringify(body)})});
    const value = await response.json();
    if (!response.ok) throw new ApiError(response.status, value.error || 'request_failed');
    return value;
  }
  async prepareCsrf() { this.csrf = (await this.request('/api/auth/csrf')).csrf_token; }
  async login(username, password) {
    // Login também é POST protegido. Nunca enviar senha antes do GET de CSRF.
    await this.prepareCsrf();
    const result = await this.request('/api/auth/login', 'POST', {username, password});
    this.csrf = result.csrf_token; // Token renovado vale para mutações E Socket.IO.
    return result;
  }
}

export class EventFeed {
  constructor(accept, max = 200) { this.accept = accept; this.max = max; this.reset(); }
  reset() { this.cursor = 0; this.items = new Map(); }
  ingest(event) {
    if (!Number.isSafeInteger(event.event_id) || event.event_id <= 0 || this.items.has(event.event_id)) return;
    this.items.set(event.event_id, event);
    this.accept(event);
    const keys = [...this.items.keys()].sort((a, b) => a - b);
    while (keys.length > this.max) this.items.delete(keys.shift());
  }
  newest() { return [...this.items.values()].sort((a, b) => b.event_id - a.event_id); }
  async replay(api, active = () => true) {
    // Só REST avança o cursor. Um push com ID maior não autoriza pular a lacuna.
    while (active()) {
      const page = await api.request(`/api/events?after_id=${this.cursor}&limit=500`);
      if (!active()) return;
      for (const event of page.events) {
        this.ingest(event);
        this.cursor = Math.max(this.cursor, event.event_id);
      }
      if (page.events.length < 500) return;
    }
  }
}

export function riskStyle(risk) {
  // O frontend apresenta o julgamento do motor; não calcula outro score.
  if (!risk || risk.score === null || risk.score === undefined) return {label: 'Sem avaliação', css: '', color: '#a8bbd1'};
  const styles = {confiável: {css: 'safe', color: '#79e0b4'},
    desconhecido: {css: 'unknown', color: '#f0d288'}, suspeito: {css: 'danger', color: '#ffa4b4'}};
  return {label: risk.classification || 'Sem classificação', ...(styles[risk.classification] || {css: '', color: '#a8bbd1'})};
}

export function graphData(topology) {
  const nodes = new Map(topology.nodes.map(device => {
    const risk = riskStyle(device.risk);
    return [device.mac, {id: device.mac, label: `${device.mac}\n${risk.label}`,
      shape: 'dot', color: {background: '#172c40', border: risk.color}, size: 23,
      font: {color: '#edf4fc', size: 14}, borderWidth: 2}];
  }));
  const edges = topology.links.map(link => {
    for (const mac of [link.source, link.target]) {
      if (!nodes.has(mac)) nodes.set(mac, {id: mac,
        label: `${mac}\n${mac === 'ff:ff:ff:ff:ff:ff' ? 'Broadcast' : 'Destino observado'}`,
        shape: 'box', color: '#26394f', font: {color: '#a8bbd1', size: 14}});
    }
    return {id: `${link.source}>${link.target}`, from: link.source, to: link.target,
      label: `${link.packets} pac.`, arrows: 'to', color: {color: '#6586a1'},
      font: {color: '#b9cee1', size: 12, strokeWidth: 0}, smooth: {type: 'continuous'}};
  });
  return {nodes: [...nodes.values()], edges};
}

export function counterInterval(before, after) {
  const unavailable = reason => ({comparable: false, reason, deltas: null});
  if (!before || !after) return unavailable('Aguardando duas leituras comparáveis.');
  if (before.run_id !== after.run_id || before.attacker_mac !== after.attacker_mac ||
      Boolean(before.simulated) !== Boolean(after.simulated)) return unavailable('Agente ou alvo mudou; inicie uma nova comparação.');
  if (!(after.timestamp > before.timestamp)) return unavailable('Leituras sem intervalo de tempo válido.');
  const names = ['seen', 'dropped', 'passed'];
  const deltas = {};
  for (const name of names) {
    const a = after.counters?.[name]?.packets, b = before.counters?.[name]?.packets;
    if (!Number.isFinite(a) || !Number.isFinite(b) || a < b || b < 0) return unavailable('Contador indisponível ou reiniciado.');
    deltas[name] = a - b;
  }
  const confirmed = [before, after].every(e => e.mitigated === true && e.blocked === true && e.arp_static_correct === true);
  const reason = !confirmed ? 'As duas leituras não confirmam ARP estático e bloqueio.' :
    deltas.passed > 0 ? 'Houve pacotes entregues após o filtro neste intervalo.' :
    deltas.seen === 0 || deltas.dropped === 0 ? 'Sem descartes com tráfego ativo: zero entregue sozinho não prova bloqueio.' :
    'Há descartes e zero pacotes entregues após o filtro neste intervalo. Ping exige verificação separada.';
  return {comparable: true, reason, deltas};
}
