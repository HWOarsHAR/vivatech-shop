/* Клиент API: хранение JWT в localStorage, автообновление access-токена по refresh. */
const API = {
  get access() { return localStorage.getItem('access'); },
  get refresh() { return localStorage.getItem('refresh'); },
  setTokens(d) {
    if (d.access) localStorage.setItem('access', d.access);
    if (d.refresh) localStorage.setItem('refresh', d.refresh);
  },
  clear() { localStorage.removeItem('access'); localStorage.removeItem('refresh'); },

  /** Обмен refresh -> новый access. true, если получилось. */
  async refreshToken() {
    if (!this.refresh) return false;
    const r = await fetch('/api/token/refresh', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({refresh: this.refresh})
    });
    if (!r.ok) { this.clear(); return false; }
    this.setTokens(await r.json());
    return true;
  },

  /** Универсальный запрос. Возвращает {ok, status, data}. */
  async request(url, {method = 'GET', body} = {}) {
    const go = () => {
      const headers = {'Content-Type': 'application/json'};
      if (this.access) headers['Authorization'] = 'Bearer ' + this.access;
      return fetch(url, {method, headers, credentials: 'include',   // cookie сессии тоже отправляем
                         body: body === undefined ? undefined : JSON.stringify(body)});
    };
    let res = await go();
    if (res.status === 401 && this.refresh && await this.refreshToken()) res = await go(); // один повтор
    let data = {};
    try { data = await res.json(); } catch (e) { /* пустое тело */ }
    return {ok: res.ok, status: res.status, data};
  }
};

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtDate = iso => iso ? new Date(iso).toLocaleString('ru-RU') : '—';
const fmtMoney = n => Number(n).toLocaleString('ru-RU', {maximumFractionDigits: 2});
