import React, { useState } from 'react';
import { SparklesCore } from './ui/sparkles';

// Компоненты формы
const FormInput = ({ label, type, name, value, onChange, placeholder, required }) => (
  <div className="form-group mb-3">
    <label htmlFor={name} className="form-label">{label}</label>
    <input
      type={type || "text"}
      className="form-control"
      id={name}
      name={name}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      required={required}
    />
  </div>
);

const FormSelect = ({ label, name, value, onChange, options, required }) => (
  <div className="form-group mb-3">
    <label htmlFor={name} className="form-label">{label}</label>
    <select 
      className="form-select" 
      id={name} 
      name={name} 
      value={value} 
      onChange={onChange}
      required={required}
    >
      <option value="">Выберите...</option>
      {options.map(option => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  </div>
);

// Основной компонент формы
const RegistrationForm = () => {
  // Состояние для многошаговой формы
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    // Личные данные (шаг 1)
    name: '',
    gender: '',
    age: '',
    height: '',
    weight: '',
    
    // Беговой опыт (шаг 2)
    experience: '',
    weeklyVolume: '',
    comfortablePace: '',
    
    // Цель (шаг 3)
    goalDistance: '',
    goalDate: '',
    targetTime: '',
    trainingDaysPerWeek: '',
    preferredTrainingDays: [],
  });

  // Опции для селектов
  const genderOptions = [
    { value: 'male', label: 'Мужской' },
    { value: 'female', label: 'Женский' },
  ];
  
  const experienceOptions = [
    { value: 'beginner', label: 'Начинающий (менее 6 месяцев)' },
    { value: 'intermediate', label: 'Средний (от 6 месяцев до 2 лет)' },
    { value: 'advanced', label: 'Продвинутый (более 2 лет)' },
  ];
  
  const comfortablePaceOptions = [
    { value: '4:30-5:30', label: '4:30-5:30 мин/км' },
    { value: '5:30-6:30', label: '5:30-6:30 мин/км' },
    { value: '6:30-7:00', label: '6:30-7:00 мин/км' },
    { value: '7+', label: 'Медленнее 7:00 мин/км' },
    { value: 'unknown', label: 'Не знаю свой темп' },
  ];
  
  const goalDistanceOptions = [
    { value: '5k', label: '5 км' },
    { value: '10k', label: '10 км' },
    { value: '21.1k', label: 'Полумарафон (21.1 км)' },
    { value: '42.2k', label: 'Марафон (42.2 км)' },
  ];
  
  const trainingDaysOptions = [
    { value: '2', label: '2 дня в неделю' },
    { value: '3', label: '3 дня в неделю' },
    { value: '4', label: '4 дня в неделю' },
    { value: '5', label: '5 дней в неделю' },
    { value: '6', label: '6 дней в неделю' },
  ];
  
  const weekdayOptions = [
    { value: 'mon', label: 'Понедельник' },
    { value: 'tue', label: 'Вторник' },
    { value: 'wed', label: 'Среда' },
    { value: 'thu', label: 'Четверг' },
    { value: 'fri', label: 'Пятница' },
    { value: 'sat', label: 'Суббота' },
    { value: 'sun', label: 'Воскресенье' },
  ];

  // Обработчики для формы
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value,
    });
  };
  
  const handleWeekdayChange = (e) => {
    const { value, checked } = e.target;
    if (checked) {
      setFormData({
        ...formData,
        preferredTrainingDays: [...formData.preferredTrainingDays, value],
      });
    } else {
      setFormData({
        ...formData,
        preferredTrainingDays: formData.preferredTrainingDays.filter(day => day !== value),
      });
    }
  };
  
  const nextStep = () => {
    setStep(step + 1);
  };
  
  const prevStep = () => {
    setStep(step - 1);
  };
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [botLink, setBotLink] = useState(null);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitError(null);
    
    try {
      // Отправляем данные в API Flask
      const response = await fetch('/api/save_profile', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Произошла ошибка при сохранении профиля');
      }
      
      // Показываем успешное сообщение
      setSuccessMessage(data.message);
      setBotLink(data.bot_link);
      
      console.log('Профиль успешно сохранен:', data);
    } catch (error) {
      console.error('Ошибка при отправке формы:', error);
      setSubmitError(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Рендеринг формы в зависимости от текущего шага
  const renderStep = () => {
    switch (step) {
      case 1:
        return (
          <>
            <h3 className="mb-4">Шаг 1: Личные данные</h3>
            <FormInput 
              label="Ваше имя" 
              name="name" 
              value={formData.name} 
              onChange={handleChange} 
              placeholder="Иван" 
              required 
            />
            
            <FormSelect 
              label="Пол" 
              name="gender" 
              value={formData.gender} 
              onChange={handleChange} 
              options={genderOptions} 
              required 
            />
            
            <FormInput 
              label="Возраст" 
              type="number" 
              name="age" 
              value={formData.age} 
              onChange={handleChange} 
              placeholder="30" 
              required 
            />
            
            <FormInput 
              label="Рост (см)" 
              type="number" 
              name="height" 
              value={formData.height} 
              onChange={handleChange} 
              placeholder="175" 
              required 
            />
            
            <FormInput 
              label="Вес (кг)" 
              type="number" 
              name="weight" 
              value={formData.weight} 
              onChange={handleChange} 
              placeholder="70" 
              required 
            />
            
            <div className="d-flex justify-content-end mt-4">
              <button type="button" className="btn btn-primary" onClick={nextStep}>
                Далее <i className="bi bi-arrow-right"></i>
              </button>
            </div>
          </>
        );
        
      case 2:
        return (
          <>
            <h3 className="mb-4">Шаг 2: Беговой опыт</h3>
            <FormSelect 
              label="Опыт бега" 
              name="experience" 
              value={formData.experience} 
              onChange={handleChange} 
              options={experienceOptions}
              required
            />
            
            <FormInput 
              label="Недельный объем бега (км)" 
              type="number" 
              name="weeklyVolume" 
              value={formData.weeklyVolume} 
              onChange={handleChange} 
              placeholder="20" 
              required 
            />
            
            <FormSelect 
              label="Комфортный темп бега" 
              name="comfortablePace" 
              value={formData.comfortablePace} 
              onChange={handleChange} 
              options={comfortablePaceOptions}
              required
            />
            
            <div className="d-flex justify-content-between mt-4">
              <button type="button" className="btn btn-outline-secondary" onClick={prevStep}>
                <i className="bi bi-arrow-left"></i> Назад
              </button>
              <button type="button" className="btn btn-primary" onClick={nextStep}>
                Далее <i className="bi bi-arrow-right"></i>
              </button>
            </div>
          </>
        );
        
      case 3:
        return (
          <>
            <h3 className="mb-4">Шаг 3: Ваша цель</h3>
            <FormSelect 
              label="Дистанция забега" 
              name="goalDistance" 
              value={formData.goalDistance} 
              onChange={handleChange} 
              options={goalDistanceOptions}
              required
            />
            
            <FormInput 
              label="Дата забега" 
              type="date" 
              name="goalDate" 
              value={formData.goalDate} 
              onChange={handleChange} 
              required 
            />
            
            <FormInput 
              label="Целевое время (формат: ч:мм:сс)" 
              type="text" 
              name="targetTime" 
              value={formData.targetTime} 
              onChange={handleChange} 
              placeholder="1:45:00"
              required 
            />
            
            <FormSelect 
              label="Сколько дней в неделю готовы тренироваться" 
              name="trainingDaysPerWeek" 
              value={formData.trainingDaysPerWeek} 
              onChange={handleChange} 
              options={trainingDaysOptions}
              required
            />
            
            <div className="form-group mb-3">
              <label className="form-label">Предпочтительные дни для тренировок</label>
              <div className="d-flex flex-wrap gap-3">
                {weekdayOptions.map(option => (
                  <div className="form-check" key={option.value}>
                    <input
                      className="form-check-input"
                      type="checkbox"
                      id={`day-${option.value}`}
                      value={option.value}
                      checked={formData.preferredTrainingDays.includes(option.value)}
                      onChange={handleWeekdayChange}
                    />
                    <label className="form-check-label" htmlFor={`day-${option.value}`}>
                      {option.label}
                    </label>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="d-flex justify-content-between mt-4">
              <button type="button" className="btn btn-outline-secondary" onClick={prevStep}>
                <i className="bi bi-arrow-left"></i> Назад
              </button>
              <button 
                type="submit" 
                className="btn btn-success" 
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                    Обработка...
                  </>
                ) : (
                  <>
                    Создать план <i className="bi bi-check-circle"></i>
                  </>
                )}
              </button>
            </div>
          </>
        );
        
      default:
        return null;
    }
  };

  return (
    <div className="container py-5">
      <div className="row justify-content-center">
        <div className="col-lg-10">
          <div className="card shadow-lg border-0">
            <div className="card-header bg-primary text-white py-3 position-relative overflow-hidden">
              <SparklesCore
                background="transparent"
                particleColor="#FFFFFF"
                particleDensity={100}
                className="absolute inset-0 z-0"
              />
              <div className="position-relative z-1">
                <h2 className="m-0 text-center">Создайте свой беговой план</h2>
                <p className="text-center mb-0 mt-2">
                  Персональный AI-тренер подготовит план специально для вас
                </p>
              </div>
            </div>
            
            <div className="card-body p-4">
              {/* Прогресс формы */}
              <div className="progress mb-4" style={{ height: '8px' }}>
                <div 
                  className="progress-bar bg-success" 
                  role="progressbar" 
                  style={{ width: `${(step / 3) * 100}%` }}
                  aria-valuenow={step} 
                  aria-valuemin="0" 
                  aria-valuemax="3"
                ></div>
              </div>
              
              {successMessage ? (
                <div className="text-center py-4">
                  <div className="alert alert-success" role="alert">
                    <h4 className="alert-heading">
                      <i className="bi bi-check-circle-fill me-2"></i>
                      Профиль успешно создан!
                    </h4>
                    <p>{successMessage}</p>
                    <hr />
                    <p className="mb-0">
                      Для продолжения перейдите в Telegram-бот и начните тренировки:
                    </p>
                    <a 
                      href={botLink} 
                      className="btn btn-primary btn-lg mt-3"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <i className="bi bi-telegram me-2"></i>
                      Перейти в Telegram
                    </a>
                  </div>
                </div>
              ) : (
                <>
                  {submitError && (
                    <div className="alert alert-danger mb-4" role="alert">
                      <i className="bi bi-exclamation-triangle-fill me-2"></i>
                      {submitError}
                    </div>
                  )}
                  <form onSubmit={handleSubmit}>
                    {renderStep()}
                  </form>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RegistrationForm;