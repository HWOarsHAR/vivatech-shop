// Нагрузочное тестирование (k6): k6 run -e BASE_URL=https://ваш-сайт tests/load/load-test.js
// Сценарий: открытие главной страницы, карточки товара и поиска, как это делает посетитель.
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8000';

export const options = {
  stages: [
    { duration: '30s', target: 10 },   // разогрев до 10 пользователей
    { duration: '1m',  target: 50 },   // рост до 50
    { duration: '30s', target: 0 },    // спад
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% запросов быстрее 500 мс
    http_req_failed: ['rate<0.01'],    // ошибок менее 1%
  },
};

export default function () {
  const home = http.get(`${BASE}/`);
  check(home, { 'главная: статус 200': (r) => r.status === 200, 'главная: быстрее 1 с': (r) => r.timings.duration < 1000 });

  const product = http.get(`${BASE}/product/1/`);
  check(product, { 'товар: статус 200': (r) => r.status === 200 });

  const search = http.get(`${BASE}/api/search?q=${encodeURIComponent('смартфон')}`);
  check(search, { 'поиск: статус 200': (r) => r.status === 200 });

  sleep(1);
}
