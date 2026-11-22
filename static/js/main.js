/* Общие скрипты: отправка форм в API, выход, живой поиск, слайдер. */

// ---------- Отправка форм с классом .js-api через fetch (после успешной валидации) ----------
function formToJson(form) {
  const o = {};
  form.querySelectorAll('input[name], textarea[name], select[name]').forEach(el => {
    if (el.type === 'checkbox') o[el.name] = el.checked;
    else if (el.type === 'number') { if (el.value !== '') o[el.name] = Number(el.value); }
    else o[el.name] = (el.type === 'password') ? el.value : el.value.trim();   // пароли не обрезаем
  });
  return o;
}
function showServerErrors(form, errors = {}) {
  form.querySelectorAll('.error').forEach(b => b.textContent = '');
  const common = form.querySelector('.form-error');
  if (common) common.textContent = '';
  Object.entries(errors).forEach(([name, msgs]) => {
    const box = form.querySelector(`[name="${name}"]`)?.closest('.field')?.querySelector('.error');
    if (box) box.textContent = msgs.join(' '); else if (common) common.textContent += msgs.join(' ') + ' ';
  });
}
document.addEventListener('submit', async e => {
  const form = e.target;
  if (!form.classList?.contains('js-api')) return;
  e.preventDefault();
  const btn = form.querySelector('button[type=submit], button:not([type])');
  if (btn) btn.disabled = true;
  const r = await API.request(form.dataset.api, {method: form.dataset.method || 'POST', body: formToJson(form)});
  if (btn) btn.disabled = false;
  if (!r.ok) {
    if (r.status === 401 && form.dataset.after !== 'login') { location.href = '/login/?next=' + location.pathname; return; }
    showServerErrors(form, r.data.errors || {__all__: [r.data.error || 'Ошибка сервера']});
    return;
  }
  if (r.data.access) API.setTokens(r.data);               // вход: сохраняем JWT
  if (form.dataset.after === 'login') await Cart.mergeFromServer();
  if (form.dataset.reset !== undefined) form.reset();
  const ok = form.querySelector('.form-ok');
  if (ok && form.dataset.success) ok.textContent = form.dataset.success;
  if (form.dataset.redirect) location.href = form.dataset.redirect;
});

// ---------- Выход ----------
document.getElementById('logout-btn')?.addEventListener('click', async () => {
  await API.request('/api/logout', {method: 'POST'});
  API.clear(); localStorage.removeItem('cart');            // чистим токены и локальную корзину
  location.href = '/';
});

// ---------- Сообщение после регистрации ----------
if (new URLSearchParams(location.search).get('registered')) {
  const n = document.getElementById('reg-ok'); if (n) n.hidden = false;
}

// ---------- Живой поиск (подсказки через /api/search) ----------
(() => {
  const input = document.querySelector('[data-live-search]'), box = document.getElementById('live-results');
  if (!input) return;
  let t;
  input.addEventListener('input', () => {
    clearTimeout(t);
    const q = input.value.trim();
    if (q.length < 2) { box.hidden = true; return; }
    t = setTimeout(async () => {
      const r = await API.request('/api/search?q=' + encodeURIComponent(q));
      if (!r.ok) { box.hidden = true; return; }
      box.innerHTML = r.data.results.slice(0, 5).map(p =>
        `<a href="${esc(p.url)}"><span>${esc(p.name)}</span><b>${fmtMoney(p.price)} ₽</b></a>`).join('')
        || '<span class="muted pad">Ничего не найдено</span>';
      box.hidden = false;
    }, 300);
  });
  document.addEventListener('click', e => { if (!e.target.closest('.search')) box.hidden = true; });
})();

// ---------- Слайдер (Задание 7): автопрокрутка, стрелки, точки, пауза при наведении ----------
(() => {
  const root = document.getElementById('slider');
  if (!root) return;
  const track = root.querySelector('.slides'), n = track.children.length, dots = root.querySelector('.dots');
  let i = 0, timer;
  for (let k = 0; k < n; k++) {
    const d = document.createElement('button'); d.setAttribute('aria-label', 'Слайд ' + (k + 1));
    d.onclick = () => go(k); dots.appendChild(d);
  }
  function go(k) {
    i = (k + n) % n;
    track.style.transform = `translateX(-${i * 100}%)`;
    [...dots.children].forEach((d, j) => d.classList.toggle('on', j === i));
  }
  const start = () => { timer = setInterval(() => go(i + 1), 4500); };
  root.querySelector('.prev').onclick = () => go(i - 1);
  root.querySelector('.next').onclick = () => go(i + 1);
  root.onmouseenter = () => clearInterval(timer); root.onmouseleave = start;
  go(0); start();
})();

// Мобильное меню
(() => {
  const button = document.getElementById('menu-toggle');
  const nav = document.getElementById('main-nav');
  if (!button || !nav) return;
  button.addEventListener('click', () => {
    const opened = nav.dataset.open !== 'true';
    nav.dataset.open = String(opened);
    button.setAttribute('aria-expanded', String(opened));
  });
})();
