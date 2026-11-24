import { el, get } from './dom.mjs';
import { badge, status, windowLabel } from './labels.mjs';
import { drawTimeline } from './timeline.mjs';

export function drawTrays(run, trayId, select) {
  const { report, reviews } = run;
  get('recipe').textContent = `工艺卡 ${report.recipe} · ${report.horizon_s} 秒`;
  get('run-title').textContent = report.id;
  get('counts').replaceChildren(
    badge('ready', `${report.trays.filter((tray) => reviews.current[tray.id]?.action === 'accept').length} 盘已签认`),
    badge('blocked', `${report.conflicts.length} 处撞占`),
    badge('neutral', run.dispatch_hash ? '交接件已冻结' : `${report.trays.length} 个料盘`),
  );
  get('trays').replaceChildren(...report.trays.map((tray) => {
    const item = el('li');
    const button = el('button');
    button.type = 'button';
    button.setAttribute('aria-current', String(tray.id === trayId));
    const reviewState = reviews.current[tray.id]?.action;
    button.append(el('strong', tray.id), badge(reviewState ?? tray.state));
    if (tray.missing_evidence_pieces?.length) {
      button.append(badge('inspect', `缺证工件 ${tray.missing_evidence_pieces.length}`));
    }
    button.addEventListener('click', () => select(tray.id));
    item.append(button);
    return item;
  }));
}

function issueLabel(issue) {
  switch (issue.reason) {
    case 'itinerary': return `工艺路线顺序不符（要求 ${issue.expected.join(' → ')}，实际 ${issue.observed.join(' → ') || '无'}）`;
    case 'gate_open': return `缺离位记录（${issue.sources.join('、')}）`;
    case 'gate_pair': return `过门记录无法成对（${issue.sources.join('、')}）`;
    case 'gate_retired': return `退役盘号之后仍有过门票，该票不产生占用（${issue.sources.join('、')}）`;
    case 'collision': return issue.conflicts.map((item) => `${item.slot} 在 ${windowLabel(item)} 与 ${item.trays.join('、')} ${item.tentative ? '疑似撞占' : '有撞占'}`).join('；');
    case 'transfer_pending': {
      const reasons = (issue.reasons || []).map(transferReason).join('、');
      return `交接 ${issue.transfer_id || issue.transfer} 待核${reasons ? `：${reasons}` : ''}`;
    }
    default: return '证据异常';
  }
}

export function transferReason(reason) {
  return {
    same_second: '同盘同秒多笔',
    duplicate_piece: '同笔重复转交',
    repeated_transfer: '同件重复转交',
    retired_tray: '复用退役盘号',
    occupied_slot: '交接时炉位仍占用',
    ownership_mismatch: '工件归属不符',
    missing_piece: '交出盘漏件',
    empty_transfer: '空交接',
  }[reason] || reason;
}

function pieceRow(piece) {
  const row = el('tr');
  const deficient = piece.deficient_stages?.length
    ? piece.deficient_stages.map((stage) => `${stage.zone}:${status[stage.state] || stage.state}`).join('，')
    : '—';
  row.append(
    el('td', piece.id),
    el('td', piece.initial_tray),
    el('td', piece.current_tray),
    el('td', piece.itinerary?.join(' → ') || '无'),
    el('td', deficient),
  );
  const state = el('td');
  state.append(badge(piece.state));
  row.append(state);
  return row;
}

export function drawPieces(tray) {
  const container = get('pieces');
  const summary = get('piece-summary');
  const pieces = tray.workpieces || tray.pieces || [];
  container.replaceChildren();
  if (!pieces.length) {
    summary.replaceChildren();
    container.append(el('p', '本炉次未登记逐件工件；继续按料盘热历核对。'));
    return;
  }
  const missing = tray.missing_evidence_pieces || pieces.filter((piece) => piece.missing_evidence).map((piece) => piece.id);
  summary.replaceChildren(badge(missing.length ? 'inspect' : 'ready',
    missing.length ? `缺证工件 ${missing.length} 件：${missing.join('、')}` : `${pieces.length} 件工件热历齐备`));
  const wrap = el('div', undefined, 'table-wrap');
  const tableNode = el('table');
  tableNode.innerHTML = '<thead><tr><th>工件</th><th>初始盘</th><th>当前盘</th><th>实际阶段顺序</th><th>缺证阶段</th><th>热历</th></tr></thead>';
  const body = el('tbody');
  body.append(...pieces.map(pieceRow));
  tableNode.append(body);
  wrap.append(tableNode);
  container.append(wrap);
}

export function drawTray(tray, horizon) {
  get('tray-title').textContent = `料盘 ${tray.id}`;
  get('tray-status').replaceChildren(badge(tray.state));
  drawTimeline(get('timeline'), tray, horizon);
  get('stages').replaceChildren(...tray.stages.map((stage) => {
    const row = el('tr');
    for (const value of [stage.label, stage.slot, windowLabel(stage), `${stage.known_s} / ${stage.duration_s} 秒`,
      `${stage.longest_s} / ${stage.min_contiguous_s} 秒`]) row.append(el('td', value));
    const result = el('td');
    result.append(badge(stage.state));
    row.append(result);
    return row;
  }));
  drawPieces(tray);
  get('issues').replaceChildren(...tray.issues.map((issue) => el('li', issueLabel(issue))));
}
