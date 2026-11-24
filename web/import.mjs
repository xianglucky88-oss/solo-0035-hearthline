import { example, write } from './api.mjs';
import { get, note } from './dom.mjs';

export function connectImport(onSaved) {
  const dialog = get('import-dialog');
  const payload = get('payload');
  const result = get('import-result');
  const buttons = ['load-example', 'preview', 'ingest'].map(get);
  let busy = false;
  const attempt = (handler) => async () => {
    if (busy) return;
    busy = true;
    for (const button of buttons) button.disabled = true;
    note(result, '正在处理…');
    try {
      await handler();
    } catch (error) {
      note(result, error.message, true);
    } finally {
      busy = false;
      for (const button of buttons) button.disabled = false;
    }
  };
  const fill = attempt(async () => {
    payload.value = await example();
    note(result, '示例资料已载入。');
  });
  buttons[0].addEventListener('click', fill);
  get('open-import').addEventListener('click', () => dialog.showModal());
  get('demo').addEventListener('click', () => { dialog.showModal(); fill(); });
  get('upload').addEventListener('change', attempt(async () => {
    const [file] = get('upload').files;
    if (!file) return;
    if (file.size > 4 * 1024 * 1024) throw new Error('文件超过 4 MiB。');
    payload.value = await file.text();
    note(result, '文件已载入。');
  }));
  buttons[1].addEventListener('click', attempt(async () => {
    const report = await write('preview', payload.value);
    const ready = report.trays.filter((tray) => tray.state === 'ready').length;
    note(result, `${report.id} 可归档。${report.trays.length} 盘中 ${ready} 盘证据齐备，发现 ${report.conflicts.length} 处撞占。`);
  }));
  buttons[2].addEventListener('click', attempt(async () => {
    const saved = await write('runs', payload.value);
    await onSaved(saved);
    dialog.close();
    note(result);
  }));
}
