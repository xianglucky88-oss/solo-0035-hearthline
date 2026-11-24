import { batchDownloadPath, downloadPath, read, runPath, write } from './api.mjs';
import { el, get, note, table } from './dom.mjs';
import { status } from './labels.mjs';

function downloadLinks(id, result, message, batchId) {
  const actions = get('handoff-actions');
  for (const suffix of ['json', 'csv']) {
    const link = el('a', `下载 ${suffix.toUpperCase()}`, 'download');
    link.href = batchId
      ? batchDownloadPath(id, batchId, suffix)
      : downloadPath(id, suffix);
    actions.append(link);
  }
  note(message, `交接摘要 ${result.dispatch_hash}`);
}

function drawBatches(id, result) {
  const body = get('handoff-body');
  const rows = result.dispatches.map((item) => [item.batch_id, item.mode === 'whole' ? '整炉' : '分批',
    item.content_hash.slice(0, 12)]);
  body.append(el('h3', '已冻结批次'), table(['批号', '方式', '交接摘要'], rows));
  for (const item of result.dispatches) {
    const group = el('div', undefined, 'batch-links');
    for (const suffix of ['json', 'csv']) {
      const link = el('a', `${item.batch_id} · ${suffix.toUpperCase()}`, 'download');
      link.href = item.mode === 'whole'
        ? downloadPath(id, suffix)
        : batchDownloadPath(id, item.batch_id, suffix);
      group.append(link);
    }
    body.append(group);
  }
}

export async function openHandoff(id, onFrozen) {
  const dialog = get('handoff-dialog');
  const message = get('handoff-result');
  const body = get('handoff-body');
  const actions = get('handoff-actions');
  body.replaceChildren();
  actions.replaceChildren();
  note(message, '正在读取…');
  if (!dialog.open) dialog.showModal();
  try {
    const result = await read(`${runPath(id)}/handoff`);

    // 整炉冻结：整炉不可再分批或补签，仅提供原整炉件下载。
    if (result.dispatch_hash && result.mode === 'whole') {
      body.append(el('p', `炉次 ${id} 已整炉冻结 · 签认记录版本 ${result.revision}`));
      downloadLinks(id, result, message);
      return;
    }

    body.append(el('p', `炉次 ${id} · 签认记录版本 ${result.revision} · 分批交接`));
    if (result.dispatches?.length) drawBatches(id, result);

    const candidateRows = [
      ...result.included.map((tray) => [tray.id, '可预核', tray.decision.reviewer]),
      ...result.excluded.map((tray) => [tray.id,
        tray.state === 'dispatched' ? `已随批 ${tray.batch} 交接` : (tray.decision ? status[tray.decision.action] : status[tray.state]),
        tray.decision?.reviewer ?? '']),
    ];
    body.append(el('h3', '料盘签认状态'), table(['料盘', '交接', '签认'], candidateRows));

    const form = el('form');
    const batchLabel = el('label');
    batchLabel.append('交接批号', Object.assign(document.createElement('input'), {
      name: 'batch', required: true, maxlength: 40, autocomplete: 'off',
      placeholder: '字母/数字开头，最多 40 位',
    }));
    const trayLabel = el('label');
    trayLabel.append('选盘（逗号或空格分隔）', Object.assign(document.createElement('input'), {
      name: 'trays', required: true, autocomplete: 'off',
      placeholder: '例如 B1, B2',
    }));
    const precheckButton = el('button', '生成预核', 'primary');
    precheckButton.type = 'button';
    form.append(batchLabel, trayLabel, precheckButton);
    body.append(el('h3', '新批次预核'), form);

    let token = null;
    let chosenBatch = null;
    const freeze = el('button', '按预核整批冻结', 'primary');
    freeze.type = 'button';
    freeze.disabled = true;
    actions.append(freeze);

    precheckButton.addEventListener('click', async () => {
      const batch = form.elements.batch.value.trim();
      const trays = form.elements.trays.value.split(/[\s,，、]+/).filter(Boolean);
      note(message);
      try {
        const pre = await write(`${runPath(id)}/handoff/precheck`, { batch, trays });
        token = pre.precheck_hash;
        chosenBatch = pre.batch;
        freeze.disabled = false;
        note(message, `预核 ${pre.batch} 已生成，含 ${pre.included.length} 盘；确认后整批冻结。`);
      } catch (error) {
        token = null;
        freeze.disabled = true;
        note(message, error.message, true);
      }
    });

    freeze.addEventListener('click', async () => {
      if (!token) return;
      freeze.disabled = true;
      try {
        const frozen = await write(`${runPath(id)}/batches`, { batch: chosenBatch, precheck_hash: token });
        note(message, `批次 ${frozen.batch} 已冻结，摘要 ${frozen.dispatch_hash.slice(0, 12)}…`);
        await onFrozen();
        await openHandoff(id, onFrozen);
      } catch (error) {
        note(message, error.message, true);
        freeze.disabled = false;
      }
    });
  } catch (error) {
    note(message, error.message, true);
  }
}
