document.addEventListener('DOMContentLoaded', function() {
    // Инициализация многошагового процесса регистрации
    const formSteps = document.querySelectorAll('.form-step');
    const nextBtns = document.querySelectorAll('.next-step');
    const prevBtns = document.querySelectorAll('.prev-step');
    let currentStep = 0;

    // Обработчики для навигации по шагам формы
    if (nextBtns.length > 0) {
        nextBtns.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Валидация полей текущего шага перед переходом
                if (validateStep(currentStep)) {
                    formSteps[currentStep].classList.remove('active');
                    currentStep++;
                    formSteps[currentStep].classList.add('active');
                    updateProgressBar();
                    
                    // Скролл наверх
                    window.scrollTo({
                        top: document.querySelector('.form-container').offsetTop - 100,
                        behavior: 'smooth'
                    });
                }
            });
        });
    }

    if (prevBtns.length > 0) {
        prevBtns.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                formSteps[currentStep].classList.remove('active');
                currentStep--;
                formSteps[currentStep].classList.add('active');
                updateProgressBar();
            });
        });
    }

    // Проверка введенного телеграм-username
    const checkTelegramBtn = document.getElementById('check-telegram');
    if (checkTelegramBtn) {
        checkTelegramBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const telegramInput = document.getElementById('telegram_username');
            const telegramValue = telegramInput.value.trim();
            const telegramError = document.getElementById('telegram-error');
            
            if (!telegramValue) {
                telegramError.textContent = 'Пожалуйста, введите ваш Telegram username';
                return;
            }
            
            // Проверка формата Telegram username
            if (!telegramValue.startsWith('@')) {
                telegramError.textContent = 'Telegram username должен начинаться с @';
                return;
            }
            
            // Проверка на существование пользователя в системе
            checkTelegramUsername(telegramValue);
        });
    }

    // Проверка существования пользователя в системе
    function checkTelegramUsername(username) {
        const telegramError = document.getElementById('telegram-error');
        const loadingIndicator = document.getElementById('telegram-loading');
        
        // Отобразить индикатор загрузки
        if (loadingIndicator) {
            loadingIndicator.style.display = 'inline-block'; 
        }
        
        fetch('/api/check_telegram_user', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ telegram_username: username })
        })
        .then(response => response.json())
        .then(data => {
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            
            if (data.exists) {
                telegramError.textContent = 'Пользователь с таким Telegram username уже существует в системе';
                telegramError.classList.add('text-danger');
            } else {
                telegramError.textContent = 'Отлично! Можно продолжить';
                telegramError.classList.remove('text-danger');
                telegramError.classList.add('text-success');
                
                // Разрешаем переход на следующий шаг
                document.getElementById('next-after-telegram').disabled = false;
            }
        })
        .catch(error => {
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            telegramError.textContent = 'Ошибка проверки. Пожалуйста, попробуйте позже';
            console.error('Error checking telegram username:', error);
        });
    }

    // Обновление индикатора прогресса
    function updateProgressBar() {
        const progressBar = document.getElementById('registration-progress');
        if (progressBar) {
            const progress = ((currentStep + 1) / formSteps.length) * 100;
            progressBar.style.width = progress + '%';
            progressBar.setAttribute('aria-valuenow', progress);
        }
    }

    // Валидация полей формы на каждом шаге
    function validateStep(step) {
        const currentForm = formSteps[step];
        const requiredFields = currentForm.querySelectorAll('[required]');
        let isValid = true;
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                isValid = false;
                const errorElement = document.getElementById(field.id + '-error');
                if (errorElement) {
                    errorElement.textContent = 'Это поле обязательно для заполнения';
                }
                field.classList.add('is-invalid');
            } else {
                field.classList.remove('is-invalid');
                const errorElement = document.getElementById(field.id + '-error');
                if (errorElement) {
                    errorElement.textContent = '';
                }
            }
        });
        
        // Дополнительные проверки для специальных полей
        if (step === 0) {
            // Проверка для Telegram username
            const telegramInput = document.getElementById('telegram_username');
            if (telegramInput && telegramInput.value.trim() && !telegramInput.value.trim().startsWith('@')) {
                isValid = false;
                const errorElement = document.getElementById('telegram-error');
                if (errorElement) {
                    errorElement.textContent = 'Telegram username должен начинаться с @';
                }
                telegramInput.classList.add('is-invalid');
            }
        }
        
        return isValid;
    }

    // Обработка формы создания профиля
    const profileForm = document.getElementById('runner-profile-form');
    if (profileForm) {
        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (!validateStep(currentStep)) {
                return;
            }
            
            // Собираем данные формы
            const formData = new FormData(profileForm);
            const profileData = {};
            
            for (const [key, value] of formData.entries()) {
                profileData[key] = value;
            }
            
            // Отправляем данные профиля на сервер
            fetch('/api/create_profile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(profileData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Переходим на страницу успеха
                    window.location.href = `/success?telegram=${encodeURIComponent(profileData.telegram_username)}`;
                } else {
                    // Отображаем ошибку
                    alert('Ошибка при создании профиля: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error creating profile:', error);
                alert('Произошла ошибка при отправке данных. Пожалуйста, попробуйте позже.');
            });
        });
    }
    
    // Обработка переключателей для выбора значений
    const toggleButtons = document.querySelectorAll('.toggle-button');
    if (toggleButtons.length > 0) {
        toggleButtons.forEach(button => {
            button.addEventListener('click', function() {
                const groupName = this.getAttribute('data-group');
                const value = this.getAttribute('data-value');
                const hiddenInput = document.querySelector(`input[name="${groupName}"]`);
                
                // Снимаем активный класс со всех кнопок в группе
                document.querySelectorAll(`.toggle-button[data-group="${groupName}"]`).forEach(btn => {
                    btn.classList.remove('active');
                });
                
                // Устанавливаем активный класс для нажатой кнопки
                this.classList.add('active');
                
                // Устанавливаем значение в скрытое поле
                if (hiddenInput) {
                    hiddenInput.value = value;
                }
            });
        });
    }
});