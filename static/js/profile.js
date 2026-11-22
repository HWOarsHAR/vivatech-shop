/* Личный кабинет: данные подгружаются из API по JWT. */
const tabs = document.querySelectorAll('.tabs [data-tab]');
function openTab(name) {
  tabs.forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab').forEach(s => s.hidden = s.id !== 'tab-' + name);
}
tabs.forEach(b => b.onclick = () => openTab(b.dataset.tab));
if (location.hash === '#orders') openTab('orders');

function unauthorized(r) {   // токена нет/истёк и refresh не помог — на страницу входа
  if (r.status === 401) { location.href = '/login/?next=/profile/'; return true; }
  return false;
}

(async () => {
  const [p, fb, orders, log] = await Promise.all([
    API.request('/api/profile'), API.request('/api/feedback'),
    API.request('/api/orders'), API.request('/api/actions?limit=30')]);
  if (unauthorized(p)) return;
  document.getElementById('p-name').value = p.data.name;
  document.getElementById('p-email').value = p.data.email || '';
  document.getElementById('p-phone').value = p.data.phone || '';
  document.getElementById('p-meta').textContent =
    `Регистрация: ${fmtDate(p.data.created_at)} · Последний вход: ${fmtDate(p.data.last_login)}`;

  document.getElementById('fb-list').innerHTML = fb.data.results?.length
    ? fb.data.results.map(f => `<div class="card"><b>${esc(f.subject)}</b>
        ${f.rating ? '· ' + '★'.repeat(f.rating) : ''} <span class="muted">· ${esc(f.status)} · ${fmtDate(f.created_at)}</span>
        <p>${esc(f.message)}</p></div>`).join('') : 'Обращений пока нет.';

  document.getElementById('orders-list').innerHTML = orders.data.results?.length
    ? orders.data.results.map(o => `<div class="card"><b>Заказ №${o.id}</b> · ${esc(o.status)} · ${fmtDate(o.created_at)}
        <ul>${o.items.map(i => `<li>${esc(i.name)} × ${i.qty} — ${fmtMoney(i.price * i.qty)} ₽</li>`).join('')}</ul>
        <b>Итого: ${fmtMoney(o.total)} ₽</b></div>`).join('') : 'Заказов пока нет.';

  document.getElementById('log-list').innerHTML = log.data.results?.length
    ? `<table class="table"><thead><tr><th>Дата</th><th>Действие</th><th>Страница</th></tr></thead>` +
      log.data.results.map(a => `<tr><td>${fmtDate(a.created_at)}</td><td>${esc(a.action)}</td><td>${esc(a.page)}</td></tr>`).join('') + '</table>'
    : 'Журнал пуст.';
})();
