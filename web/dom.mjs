export const get = (id) => document.getElementById(id);

export function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

export function note(node, message = '', error = false) {
  node.textContent = message;
  node.hidden = !message;
  node.dataset.error = String(error);
}

export function table(headings, rows) {
  const wrap = el('div', undefined, 'table-wrap');
  const result = el('table');
  const header = result.createTHead().insertRow();
  header.append(...headings.map((label) => el('th', label)));
  const body = result.createTBody();
  for (const row of rows) body.insertRow().append(...row.map((value) => el('td', value)));
  wrap.append(result);
  return wrap;
}
