import { el } from './dom.mjs';

export const status = {
  ready: '证据齐备', inspect: '需复核', blocked: '路线留置', retired: '盘号退役', empty: '空盘',
  effective: '交接生效', transfer_pending: '交接待核',
  qualified: '达标', incomplete: '证据缺口', short: '达标时长不足',
  accept: '签认通过', hold: '暂缓', pending: '未签认',
};

const tones = { ready: 'ready', qualified: 'ready', accept: 'ready', effective: 'ready',
  inspect: 'inspect', incomplete: 'inspect', short: 'inspect', hold: 'inspect',
  blocked: 'blocked', transfer_pending: 'blocked', retired: 'neutral', empty: 'neutral' };

export const bands = { in_band: '温度带内', out_of_band: '温度带外', unknown: '证据缺口' };
export const gaps = { outside_samples: '无相邻样点', sample_gap: '采样间隔过长',
  sample_invalid: '样点质量标记无效', uncalibrated: '缺有效校准' };
export const windowLabel = (piece) => `${piece.from}–${piece.to} 秒`;

export function badge(key, label = status[key]) {
  const node = el('span', label, 'badge');
  node.dataset.tone = tones[key] || 'neutral';
  return node;
}
