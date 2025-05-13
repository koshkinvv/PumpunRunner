import React from 'react';
import ReactDOM from 'react-dom';
import RegistrationForm from '../components/RegistrationForm';

// Функция для инициализации React-компонента формы регистрации
function initRegistrationForm() {
  const registrationFormContainer = document.getElementById('react-registration-form');
  
  if (registrationFormContainer) {
    ReactDOM.render(
      <React.StrictMode>
        <RegistrationForm />
      </React.StrictMode>,
      registrationFormContainer
    );
  }
}

// Загружаем компонент после загрузки DOM
document.addEventListener('DOMContentLoaded', () => {
  initRegistrationForm();
});

// Экспортируем инициализирующую функцию для возможности ручного вызова
window.initRegistrationForm = initRegistrationForm;