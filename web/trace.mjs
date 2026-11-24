import { el } from './dom.mjs';
import { bands, gaps, windowLabel } from './labels.mjs';

const temperature = (value) => value === null || value === undefined ? '—' : `${(value / 10).toFixed(1)} °C`;

function section(container, title, headings, rows) {
  container.append(el('h3', title), rows.length ? table(headings, rows) : el('p', '没有关联记录。'));
}

function table(headings, rows) {
  const wrap = el('div', undefined, 'table-wrap');
  const tableNode = el('table');
  const head = tableNode.createTHead().insertRow();
  head.append(...headings.map((label) => el('th', label)));
  const body = tableNode.createTBody();
  for (const row of rows) {
    const tr = body.insertRow();
    for (const value of row) tr.append(value instanceof Node ? value : el('td', String(value ?? '—')));
  }
  wrap.append(tableNode);
  return wrap;
}

function stageRows(stages) {
  return (stages || []).flatMap((stage) => (stage.slices || []).map((part) => [
    stage.id || stage.piece || '—',
    stage.zone || '—',
    stage.slot || '—',
    windowLabel(part),
    gaps[part.reason] || bands[part.status] || part.status,
    temperature(part.tenth),
    (part.sources || []).join(' · ') || '—',
    part.calibration || '—',
  ]));
}

const transferReason = (reason) => ({
  same_second: '同盘同秒多笔',
  duplicate_piece: '同笔重复转交',
  repeated_transfer: '同件重复转交',
  retired_tray: '复用退役盘号',
  occupied_slot: '炉位仍占用',
  ownership_mismatch: '归属不符',
  missing_piece: '漏件',
  empty_transfer: '空交接',
}[reason] || reason);

function transferRows(transfers) {
  return (transfers || []).map((item) => [
    item.id,
    item.at,
    item.state === 'effective' ? '生效' : '待核',
    (item.reasons || []).map(transferReason).join('、') || '—',
    (item.missing_pieces || []).join('、') || '—',
    (item.occupied_trays || []).join('、') || '—',
    (item.retired_trays || []).join('、') || '—',
  ]);
}

function commonSections(container, detail, stageOwner) {
  section(container, '交接记录', ['编号', '秒', '结论', '原因', '缺件', '占炉盘', '退役盘'],
    transferRows(detail.transfers));
  section(container, `${stageOwner}驻留测温凭证`, ['归属', '阶段', '炉位', '范围', '判定', '校正后', '样点', '校准'],
    stageRows(detail.tray ? detail.tray.stages : detail.piece?.stages));
  section(container, '过门原票', ['票号', '料盘', '炉位', '炉次秒', '动作'],
    (detail.events || []).map((event) => [event.id, event.tray, event.slot, event.at,
      event.kind === 'enter' ? '入位' : '离位']));
  section(container, '样点原值', ['记录', '测点', '炉次秒', '原温', '质量'],
    (detail.readings || []).map((row) => [row.id, row.probe, row.at, temperature(row.tenth),
      row.valid ? '有效' : '无效']));
  section(container, '校准原票', ['记录', '测点', '生效范围', '温度偏移'],
    (detail.calibrations || []).map((row) => [row.id, row.probe, windowLabel(row),
      temperature(row.offset_tenth)]));
}

export function showTrace(container, detail) {
  container.replaceChildren();
  if (detail.piece && !detail.tray) {
    const piece = detail.piece;
    container.append(el('h3', `工件 ${piece.id} · 当前盘 ${piece.current_tray}`));
    container.append(el('p', `实际阶段顺序：${piece.itinerary?.join(' → ') || '无'}；热历${piece.ready ? '齐备' : '缺证或顺序不符'}`));
    commonSections(container, detail, '本工件');
    return;
  }

  commonSections(container, detail, '本盘');
  for (const pieceTrace of detail.piece_traces || []) {
    container.append(el('h3', `工件 ${pieceTrace.piece.id} 的逐件凭证`));
    section(container, `${pieceTrace.piece.id} 交接`, ['编号', '秒', '结论', '原因', '缺件', '占炉盘', '退役盘'],
      transferRows(pieceTrace.transfers));
    section(container, `${pieceTrace.piece.id} 驻留测温`, ['工件', '阶段', '炉位', '范围', '判定', '校正后', '样点', '校准'],
      stageRows(pieceTrace.piece.stages));
  }
}
