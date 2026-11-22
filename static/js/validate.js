/* Классическая клиентская валидация: атрибуты HTML5 (required, pattern, minlength, type=email…)
   + Constraint Validation API. Формы с классом .js-validate имеют атрибут novalidate,
   поэтому сообщения показываем сами — на русском, под полем. */
function fieldMessage(el) {
  const v = el.validity;
  if (v.valueMissing) return el.dataset.msg || (el.type === 'checkbox' ? 'Необходимо согласие' : 'Обязательное поле');
  if (v.typeMismatch) return el.dataset.msg || 'Некорректное значение (проверьте формат)';
  if (v.patternMismatch) return el.dataset.msg || 'Неверный формат';
  if (v.tooShort) return `Минимум ${el.minLength} симв.`;
  if (v.tooLong) return `Максимум ${el.maxLength} симв.`;
  if (v.rangeUnderflow || v.rangeOverflow) return el.dataset.msg || `Допустимо от ${el.min} до ${el.max}`;
  if (v.stepMismatch || v.badInput) return el.dataset.msg || 'Введите целое число';
  return el.validationMessage;
}

function validateField(el) {
  el.setCustomValidity('');
  // minlength проверяется браузером только при ручном вводе — дублируем программно
  if (el.minLength > 0 && el.value && el.value.length < el.minLength)
    el.setCustomValidity(`Минимум ${el.minLength} симв.`);
  // data-match="#id" — значение должно совпадать с другим полем (подтверждение пароля)
  if (el.dataset.match) {
    const other = el.form.querySelector(el.dataset.match);
    if (other && el.value !== other.value) el.setCustomValidity('Пароли не совпадают');
  }
  if (el.dataset.oneof) {
    const other = el.form.querySelector(el.dataset.oneof);
    if (other && !el.value.trim() && !other.value.trim())
      el.setCustomValidity('Укажите email или телефон');
  }
  const box = el.closest('.field')?.querySelector('.error');
  const ok = el.checkValidity();
  if (box) box.textContent = ok ? '' : (el.validity.customError ? el.validationMessage : fieldMessage(el));
  el.classList.toggle('invalid', !ok);
  return ok;
}

function validateForm(form) {
  let ok = true, first = null;
  form.querySelectorAll('input[name], textarea[name], select[name]').forEach(el => {
    if (el.type === 'hidden') return;
    if (!validateField(el)) { ok = false; first = first || el; }
  });
  if (first) first.focus();
  return ok;
}

// Перехват отправки (фаза capture): невалидную форму не отправляем
document.addEventListener('submit', e => {
  const f = e.target;
  if (f.classList?.contains('js-validate') && !validateForm(f)) {
    e.preventDefault(); e.stopImmediatePropagation();
  }
}, true);

// «Живая» проверка при вводе/потере фокуса
document.addEventListener('input', e => {
  const el = e.target;
  if (el.form?.classList.contains('js-validate') && el.name) {
    validateField(el);
    // при изменении пароля перепроверяем поле подтверждения
    el.form.querySelectorAll(`[data-match="#${el.id}"]`).forEach(validateField);
  }
});
document.addEventListener('focusout', e => {
  const el = e.target;
  if (el.form?.classList.contains('js-validate') && el.name && el.value) validateField(el);
});
