/* Страница корзины: отрисовка, изменение количества, оформление заказа. */
function renderCart() {
  const items = Object.values(Cart.load());
  document.getElementById('cart-empty').hidden = items.length > 0;
  document.getElementById('cart-box').hidden = items.length === 0;
  document.getElementById('cart-rows').innerHTML = items.map(i => `
    <tr><td><img src="${esc(i.image)}" width="56" alt=""></td><td>${esc(i.name)}</td>
    <td>${fmtMoney(i.price)} ₽</td>
    <td><button class="qty" data-id="${esc(i.id)}" data-d="-1">−</button> ${i.qty}
        <button class="qty" data-id="${esc(i.id)}" data-d="1">+</button></td>
    <td>${fmtMoney(i.price * i.qty)} ₽</td>
    <td><button class="link danger" data-del="${esc(i.id)}">Удалить</button></td></tr>`).join('');
  document.getElementById('cart-total').textContent = fmtMoney(Cart.total());
}
document.addEventListener('cart:changed', renderCart);
document.getElementById('cart-rows').addEventListener('click', e => {
  const q = e.target.closest('[data-d]'), d = e.target.closest('[data-del]');
  if (q) Cart.setQty(q.dataset.id, (Cart.load()[q.dataset.id]?.qty || 0) + Number(q.dataset.d));
  if (d) Cart.remove(d.dataset.del);
});
document.getElementById('clear-cart').onclick = () => Cart.clear();
document.getElementById('checkout').onclick = async () => {
  const err = document.getElementById('cart-error'); err.textContent = '';
  if (!API.access) { location.href = '/login/?next=/cart/'; return; }      // заказ — только для авторизованных
  const consent = document.querySelector('[name="consent"]')?.checked;
  const third = document.querySelector('[name="consent_third"]')?.checked;
  const terms = document.querySelector('[name="terms"]')?.checked;
  if (!consent || !third || !terms) {
    err.textContent = 'Отметьте все три обязательных согласия перед оформлением заказа.';
    return;
  }
  await Cart.sync();                                                       // фиксируем корзину в БД
  const r = await API.request('/api/orders', {method: 'POST',
    body: {consent, consent_third: third, terms}});
  if (r.ok) { Cart.save({}, false); location.href = '/profile/#orders'; }
  else if (r.status === 401) location.href = '/login/?next=/cart/';
  else err.textContent = r.data.error || 'Не удалось оформить заказ';
};
renderCart();
Cart.sync();   // подтянуть актуальные цены/наличие
