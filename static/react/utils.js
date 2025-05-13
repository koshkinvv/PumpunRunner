// Утилитарные функции для работы с React-компонентами

// Аналог cn (classnames) функции для объединения классов
function cn(...classes) {
  return classes.filter(Boolean).join(' ');
}

// Функция для валидации формата электронной почты
function validateEmail(email) {
  const re = /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
  return re.test(String(email).toLowerCase());
}

// Функция для валидации времени в формате ЧЧ:ММ:СС
function validateTime(time) {
  const re = /^([0-9]):([0-5][0-9]):([0-5][0-9])$|^([0-9]{2}):([0-5][0-9]):([0-5][0-9])$/;
  return re.test(String(time));
}

// Форматирование данных для отправки в API
function formatProfileData(formData) {
  return {
    name: formData.name,
    gender: formData.gender,
    age: parseInt(formData.age, 10),
    height: parseInt(formData.height, 10),
    weight: parseInt(formData.weight, 10),
    experience: formData.experience,
    weekly_volume: parseInt(formData.weeklyVolume, 10),
    comfortable_pace: formData.comfortablePace,
    goal_distance: formData.goalDistance,
    goal_date: formData.goalDate,
    target_time: formData.targetTime,
    training_days_per_week: parseInt(formData.trainingDaysPerWeek, 10),
    preferred_training_days: formData.preferredTrainingDays.join(',')
  };
}

// Экспортируем утилиты
window.utils = {
  cn,
  validateEmail,
  validateTime,
  formatProfileData
};