import { el, table } from './dom.mjs';
import { bands, gaps, windowLabel } from './labels.mjs';

const temperature = (value) => value === null ? '—' : `${(value / 10).toFixed(1)} °C`;

function section(container, title, headings, rows) {
  container.append(el('h3', title), rows.length ? table(headings, rows) : el('p', '没有关联记录。'));
}

export function showTrace(container, detail) {
  container.replaceChildren();
  section(container, '驻留测温凭证', ['炉位', '范围', '判定', '校正后', '样点', '校准'],
    detail.tray.stages.flatMap((stage) => stage.slices.map((part) => [stage.slot, windowLabel(part),
      gaps[part.reason] || bands[part.status], temperature(part.tenth), part.sources.join(' · ') || '—', part.calibration || '—'])));
  section(container, '过门原票', ['票号', '料盘', '炉位', '炉次秒', '动作'],
    detail.events.map((event) => [event.id, event.tray, event.slot, event.at, event.kind === 'enter' ? '入位' : '离位']));
  section(container, '样点原值', ['记录', '测点', '炉次秒', '原温', '质量'],
    detail.readings.map((row) => [row.id, row.probe, row.at, temperature(row.tenth), row.valid ? '有效' : '无效']));
  section(container, '校准原票', ['记录', '测点', '生效范围', '温度偏移'],
    detail.calibrations.map((row) => [row.id, row.probe, windowLabel(row), temperature(row.offset_tenth)]));
}
