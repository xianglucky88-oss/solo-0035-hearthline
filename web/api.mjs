const prefix = '/api/hearth/';
export const runPath = (id) => `runs/${encodeURIComponent(id)}`;
export const downloadPath = (id, suffix) => `${prefix}${runPath(id)}/dispatch.${suffix}`;

async function request(path, init) {
  const reply = await fetch(prefix + path, init);
  if (!reply.ok) {
    let message = `请求失败（${reply.status}）`;
    if (reply.headers.get('content-type')?.includes('application/json')) message = (await reply.json()).error;
    const error = new Error(message);
    error.status = reply.status;
    throw error;
  }
  return reply;
}

export async function read(path) {
  return (await request(path)).json();
}

export async function example() {
  return (await request('example')).text();
}

export async function write(path, value) {
  const body = typeof value === 'string' ? value : JSON.stringify(value);
  return (await request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body })).json();
}
