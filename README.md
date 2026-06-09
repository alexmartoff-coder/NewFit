# NewFit
Бот для тренера фитнес/спорт-зала для записи на тренировки, питание, калории и т.д.

## Исправление базы данных (Railway)

Если вы столкнулись с ошибкой внешнего ключа в таблице `time_slots` (ошибка: `Key (trainer_profile_id)=(X) is not present in table "users"`), необходимо вручную применить исправление в консоли базы данных:

1. Откройте ваш проект в Railway.
2. Перейдите в настройки базы данных PostgreSQL -> вкладка **Data** или **Query**.
3. Выполните следующий SQL-запрос:

```sql
-- 1. Удаляем старый (неправильный) внешний ключ
ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_trainer_id_fkey;
ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_trainer_profile_id_fkey;

-- 2. Добавляем правильный внешний ключ к trainer_profiles.id
ALTER TABLE time_slots
ADD CONSTRAINT time_slots_trainer_profile_id_fkey
FOREIGN KEY (trainer_profile_id)
REFERENCES trainer_profiles(id)
ON DELETE CASCADE;
```
