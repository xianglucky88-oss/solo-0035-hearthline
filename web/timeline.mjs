import { el } from './dom.mjs';
import { bands, windowLabel } from './labels.mjs';

export function drawTimeline(container, tray, horizon) {
  const axis = el('div', undefined, 'axis');
  for (const tick of new Set([0, Math.floor(horizon / 2), horizon])) axis.append(el('span', `${tick} 秒`));
  container.replaceChildren(axis);
  if (!tray.stages.length) container.append(el('p', '没有成对的过门证据。'));
  for (const stage of tray.stages) {
    const lane = el('div', undefined, 'lane');
    lane.setAttribute('aria-hidden', 'true');
    for (const part of stage.timeline) {
      const node = el('span', undefined, 'segment');
      node.dataset.state = part.status;
      node.title = `${windowLabel(part)} · ${bands[part.status]}`;
      node.style.left = `${100 * part.from / horizon}%`;
      node.style.width = `${100 * (part.to - part.from) / horizon}%`;
      lane.append(node);
    }
    container.append(el('p', `${stage.label} · ${stage.slot}`, 'lane-label'), lane);
  }
  const legend = el('div', undefined, 'legend');
  for (const [key, text] of Object.entries(bands)) {
    const wrap = el('span');
    const mark = el('i', undefined, 'swatch');
    mark.dataset.state = key;
    wrap.append(mark, document.createTextNode(text));
    legend.append(wrap);
  }
  container.append(legend);
}
