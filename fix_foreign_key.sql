-- Скрипт для исправления неправильного внешнего ключа в таблице time_slots
-- Ошибка: trainer_profile_id ссылается на users.id вместо trainer_profiles.id

-- 1. Удаляем старый (неправильный) внешний ключ
-- Примечание: имя константы может отличаться, пробуем типичные варианты
ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_trainer_id_fkey;
ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_trainer_profile_id_fkey;

-- 2. Добавляем правильный внешний ключ к trainer_profiles.id
ALTER TABLE time_slots
ADD CONSTRAINT time_slots_trainer_profile_id_fkey
FOREIGN KEY (trainer_profile_id)
REFERENCES trainer_profiles(id)
ON DELETE CASCADE;
