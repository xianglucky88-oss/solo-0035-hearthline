import { el, get } from './dom.mjs';
import { badge, windowLabel } from './labels.mjs';
import { drawTimeline } from './timeline.mjs';

export function drawTrays(run, trayId, select) {
  const { report, reviews } = run;
  get('recipe').textContent = `工艺卡 ${report.recipe} · ${report.horizon_s} 秒`;
  get('run-title').textContent = report.id;
  get('counts').replaceChildren(
    badge('ready', `${report.trays.filter((tray) => reviews.current[tray.id]?.action === 'accept').length} 盘已签认`),
    badge('blocked', `${report.conflicts.length} 处撞占`),
    badge('neutral', run.whole_frozen
      ? '整炉交接件已冻结'
      : `${Object.keys(run.dispatched ?? {}).length} / ${report.trays.length} 盘已交接`),
  );
  get('trays').replaceChildren(...report.trays.map((tray) => {
    const item = el('li');
    const button = el('button');
    button.type = 'button';
    button.setAttribute('aria-current', String(tray.id === trayId));
    const batch = run.dispatched?.[tray.id];
    button.append(el('strong', tray.id),
      batch ? badge('neutral', `已交接 · ${batch}`) : badge(reviews.current[tray.id]?.action ?? tray.state));
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
    case 'collision': return issue.conflicts.map((item) => `${item.slot} 在 ${windowLabel(item)} 与 ${item.trays.join('、')} ${item.tentative ? '疑似撞占' : '有撞占'}`).join('；');
    default: return '证据异常';
  }
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
  get('issues').replaceChildren(...tray.issues.map((issue) => el('li', issueLabel(issue))));
}
