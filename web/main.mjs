import { read, runPath, write } from './api.mjs';
import { get, el, note } from './dom.mjs';
import { openHandoff } from './handoff.mjs';
import { connectImport } from './import.mjs';
import { drawReviews } from './reviews.mjs';
import { showTrace } from './trace.mjs';
import { drawTray, drawTrays } from './trays.mjs';

const runs = get('runs');
const notice = get('notice');
const trace = get('trace');
const traceSection = get('trace-section');
const form = get('review-form');
let current = null;
let trayId;
let runSequence = 0;
let traceSequence = 0;
let offset = 0;
let submitting = false;

function selectTray(id) {
  const changed = trayId !== id;
  trayId = id;
  const tray = current.report.trays.find((row) => row.id === id);
  drawTrays(current, trayId, selectTray);
  drawTray(tray, current.report.horizon_s);
  drawReviews(current, tray, submitting);
  if (changed) {
    traceSequence++;
    form.elements.note.value = '';
    traceSection.open = false;
    trace.replaceChildren();
  }
}

async function selectRun(id, preferredTray = trayId) {
  const token = ++runSequence;
  const selected = await read(runPath(id));
  if (token !== runSequence) return;
  if (current?.report.id !== id) trayId = undefined;
  current = selected;
  runs.value = id;
  get('blank').hidden = true;
  get('workspace').hidden = false;
  get('handoff').disabled = false;
  get('replay').disabled = false;
  const next = current.report.trays.find((row) => row.id === preferredTray) || current.report.trays[0];
  selectTray(next.id);
}

async function loadRuns(preferred, append = false) {
  offset = append ? offset + 30 : 0;
  const result = await read(`runs?offset=${offset}`);
  if (!append) runs.replaceChildren();
  for (const entry of result) {
    if (![...runs.options].some((option) => option.value === entry.id)) runs.add(new Option(entry.id, entry.id));
  }
  if (preferred && ![...runs.options].some((option) => option.value === preferred)) runs.add(new Option(preferred, preferred));
  get('older').hidden = result.length < 30;
  if (!runs.options.length) {
    runs.add(new Option('无归档', ''));
    get('blank').hidden = false;
    get('handoff').disabled = get('replay').disabled = true;
    return;
  }
  if (!append) await selectRun(preferred || runs.options[0].value);
}

function task(action) {
  return async () => {
    note(notice);
    try { await action(); } catch (error) { note(notice, error.message, true); }
  };
}

connectImport(async (entry) => {
  await loadRuns(entry.id);
  note(notice, entry.created ? '炉次已归档。' : '已打开同一份归档。');
});
runs.addEventListener('change', task(async () => selectRun(runs.value)));
get('older').addEventListener('click', task(async () => loadRuns(undefined, true)));
get('replay').addEventListener('click', task(async () => {
  const result = await read(`${runPath(current.report.id)}/replay`);
  note(notice, result.ok ? '原始证据和分析结果复算一致。' + (result.dispatch_match ? '交接摘要一致。' : '') : '存档复算出现差异。', !result.ok);
}));
get('handoff').addEventListener('click', task(async () => {
  const id = current.report.id;
  await openHandoff(id, () => selectRun(id));
}));
traceSection.addEventListener('toggle', async () => {
  if (!traceSection.open || !current) return;
  const token = ++traceSequence;
  trace.replaceChildren(el('p', '正在读取…'));
  try {
    const detail = await read(`${runPath(current.report.id)}/trace/${encodeURIComponent(trayId)}`);
    if (token === traceSequence) showTrace(trace, detail);
  } catch (error) {
    if (token === traceSequence) note(trace, error.message, true);
  }
});
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (submitting || !event.submitter) return;
  const fields = new FormData(form);
  const id = current.report.id;
  const activeTray = trayId;
  const revision = current.reviews.revision;
  submitting = true;
  selectTray(trayId);
  note(notice);
  try {
    await write(`${runPath(id)}/reviews/${encodeURIComponent(activeTray)}`, {
      revision, action: event.submitter.value, reviewer: fields.get('reviewer'), note: fields.get('note'),
    });
    if (id === current.report.id) {
      if (trayId === activeTray) form.elements.note.value = '';
      await selectRun(id);
    }
    note(notice, '签认记录已保存。');
  } catch (error) {
    note(notice, error.message, true);
    if (error.status === 409 && id === current.report.id) {
      try { await selectRun(id); } catch (refreshError) { note(notice, refreshError.message, true); }
    }
  } finally {
    submitting = false;
    selectTray(trayId);
  }
});
for (const button of document.querySelectorAll('[data-close]')) {
  button.addEventListener('click', () => get(button.dataset.close).close());
}
await task(async () => loadRuns())();
