import { get, el } from './dom.mjs';
import { badge, status } from './labels.mjs';

export function drawReviews(run, tray, busy) {
  const form = get('review-form');
  const active = run.reviews.current[tray.id];
  get('review-status').replaceChildren(run.dispatch_hash ? badge('neutral', '已冻结') : badge(active?.action ?? 'pending'));
  for (const element of form.elements) element.disabled = Boolean(run.dispatch_hash) || busy;
  form.querySelector('button[value="accept"]').disabled ||= tray.state !== 'ready';
  const items = run.reviews.events.filter((event) => event.tray === tray.id).reverse();
  get('review-history').replaceChildren(...(items.length ? items.map((event) => el('li',
    `第 ${event.revision} 次 · ${status[event.action]} · ${event.reviewer} · ${event.note}`)) : [el('li', '还没有签认记录。')]));
}
