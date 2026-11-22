/* Корзина (Задание 7): localStorage + синхронизация с сессией/БД через /api/cart. */
const Cart = {
  load() { try { return JSON.parse(localStorage.getItem('cart')) || {}; } catch (e) { return {}; } },
  save(cart, sync = true) {
    localStorage.setItem('cart', JSON.stringify(cart));
    this.badge();
    document.dispatchEvent(new Event('cart:changed'));
    if (sync) this.scheduleSync();
  },
  count() { return Object.values(this.load()).reduce((s, i) => s + i.qty, 0); },
  total() { return Object.values(this.load()).reduce((s, i) => s + i.price * i.qty, 0); },
  badge() { const b = document.getElementById('cart-count'); if (b) b.textContent = this.count(); },

  add(item) {
    const c = this.load();
    c[item.id] = c[item.id] ? {...c[item.id], qty: Math.min(99, c[item.id].qty + 1)} : {...item, qty: 1};
    this.save(c);
  },
  setQty(id, qty) {
    const c = this.load();
    if (!c[id]) return;
    if (qty < 1) delete c[id]; else c[id].qty = Math.min(99, qty);
    this.save(c);
  },
  remove(id) { this.setQty(id, 0); },
  clear() { this.save({}); },

  scheduleSync() { clearTimeout(this._t); this._t = setTimeout(() => this.sync(), 500); },

  /** Отправляет корзину на сервер (сессия + БД, если есть JWT) и принимает «эталонные» цены. */
  async sync() {
    const items = Object.values(this.load()).map(i => ({product_id: Number(i.id), qty: i.qty}));
    const r = await API.request('/api/cart', {method: 'PUT', body: {items}});
    if (r.ok) this.replaceFromServer(r.data.items);
    return r;
  },
  replaceFromServer(items) {
    const c = {};
    items.forEach(i => c[i.id] = {id: i.id, name: i.name, price: i.price, image: i.image, qty: i.qty});
    this.save(c, false);
  },
  /** После входа: объединяем локальную корзину с сохранённой в БД (берём большее количество). */
  async mergeFromServer() {
    const r = await API.request('/api/cart');
    if (!r.ok) return;
    const c = this.load();
    r.data.items.forEach(i => {
      c[i.id] = c[i.id] ? {...c[i.id], qty: Math.max(c[i.id].qty, i.qty)}
                        : {id: i.id, name: i.name, price: i.price, image: i.image, qty: i.qty};
    });
    this.save(c, false);
    await this.sync();
  }
};

document.addEventListener('click', e => {           // кнопки «В корзину» (делегирование событий)
  const b = e.target.closest('[data-add-to-cart]');
  if (!b) return;
  Cart.add({id: b.dataset.id, name: b.dataset.name, price: Number(b.dataset.price), image: b.dataset.image});
  const old = b.textContent; b.textContent = '✓ Добавлено'; setTimeout(() => b.textContent = old, 900);
});
Cart.badge();
