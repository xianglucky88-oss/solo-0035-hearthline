import { get, el } from './dom.mjs';
import { badge, status } from './labels.mjs';

export function drawReviews(run, tray, busy) {
  const form = get('review-form');
  const active = run.reviews.current[tray.id];
  const wholeFrozen = Boolean(run.whole_frozen);
  const trayBatch = run.dispatched?.[tray.id];
  const locked = wholeFrozen || Boolean(trayBatch);
  const lockLabel = wholeFrozen ? '整炉已冻结' : `已随批 ${trayBatch} 交接`;
  get('review-status').replaceChildren(
    locked ? badge('neutral', lockLabel) : badge(active?.action ?? 'pending'));
  for (const element of form.elements) element.disabled = locked || busy;
  form.querySelector('button[value="accept"]').disabled ||= tray.state !== 'ready';
  const items = run.reviews.events.filter((event) => event.tray === tray.id).reverse();
  get('review-history').replaceChildren(...(items.length ? items.map((event) => el('li',
    `第 ${event.revision} 次 · ${status[event.action]} · ${event.reviewer} · ${event.note}`)) : [el('li', '还没有签认记录。')]));
}
