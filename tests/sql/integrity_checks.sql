-- Контрольные запросы целостности БД (DBeaver / pgAdmin). Ожидаемый результат — 0 строк в каждом запросе.

-- 1. «Сиротские» записи (нарушение внешних ключей)
SELECT o.id AS order_id FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE u.id IS NULL;
SELECT f.id AS feedback_id FROM feedback f LEFT JOIN users u ON f.user_id = u.id WHERE u.id IS NULL;
SELECT i.id AS order_item_id FROM order_items i LEFT JOIN orders o ON i.order_id = o.id WHERE o.id IS NULL;
SELECT c.id AS cart_item_id FROM cart_items c LEFT JOIN products p ON c.product_id = p.id WHERE p.id IS NULL;
SELECT s.id AS session_id FROM user_sessions s LEFT JOIN users u ON s.user_id = u.id WHERE u.id IS NULL;

-- 2. Дубликаты по уникальным полям
SELECT email, COUNT(*) FROM users WHERE email IS NOT NULL GROUP BY email HAVING COUNT(*) > 1;
SELECT phone, COUNT(*) FROM users WHERE phone IS NOT NULL GROUP BY phone HAVING COUNT(*) > 1;
SELECT alias, COUNT(*) FROM products GROUP BY alias HAVING COUNT(*) > 1;

-- 3. Пустые обязательные поля
SELECT id FROM users WHERE (email IS NULL OR email = '') AND (phone IS NULL OR phone = '');
SELECT id FROM users WHERE password_hash IS NULL OR password_hash = '';
SELECT id FROM products WHERE name IS NULL OR name = '';

-- 4. Нарушения бизнес-ограничений
SELECT id, price FROM products WHERE price < 0;
SELECT id, rating FROM feedback WHERE rating IS NOT NULL AND (rating < 1 OR rating > 5);
SELECT id, quantity FROM cart_items WHERE quantity < 1 OR quantity > 99;

-- 5. Пароли хранятся хэшами bcrypt (все строки должны начинаться с $2): запрос вернёт нарушителей
SELECT id, email FROM users WHERE password_hash NOT LIKE '$2%';

-- 6. Сумма заказа равна сумме позиций (расхождения)
SELECT o.id, o.total, SUM(i.price * i.quantity) AS items_total
FROM orders o JOIN order_items i ON i.order_id = o.id
GROUP BY o.id, o.total HAVING o.total <> SUM(i.price * i.quantity);

-- 6a. Справочно (строки ожидаемы): количество записей по таблицам
SELECT 'users' AS t, COUNT(*) FROM users UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders UNION ALL SELECT 'feedback', COUNT(*) FROM feedback;
