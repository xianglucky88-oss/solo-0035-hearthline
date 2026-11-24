import { downloadPath, read, runPath, write } from './api.mjs';
import { el, get, note, table } from './dom.mjs';
import { status } from './labels.mjs';

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
    body.replaceChildren(el('p', `炉次 ${id} · 签认记录版本 ${result.revision}`), table(
      ['料盘', '交接', '签认'], [
        ...result.included.map((tray) => [tray.id, '列入', tray.decision.reviewer]),
        ...result.excluded.map((tray) => [tray.id, '暂不列入', tray.decision ? status[tray.decision.action] : status[tray.state]]),
      ]));
    if (result.dispatch_hash) {
      note(message, `交接摘要 ${result.dispatch_hash}`);
      for (const suffix of ['json', 'csv']) {
        const link = el('a', `下载 ${suffix.toUpperCase()}`, 'download');
        link.href = downloadPath(id, suffix);
        actions.append(link);
      }
      return;
    }
    const freeze = el('button', '确认冻结交接件', 'primary');
    freeze.type = 'button';
    freeze.disabled = !result.included.length;
    note(message, result.included.length ? '冻结后保留本次清单和签认，停止该炉次的新签认。' : '至少需一盘签认通过。');
    freeze.addEventListener('click', async () => {
      freeze.disabled = true;
      try {
        await write(`${runPath(id)}/dispatch`, { revision: result.revision });
        await onFrozen();
        await openHandoff(id, onFrozen);
      } catch (error) {
        note(message, error.message, true);
        freeze.disabled = false;
      }
    });
    actions.append(freeze);
  } catch (error) {
    note(message, error.message, true);
  }
}
