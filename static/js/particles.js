/**
 * Эффект "звездного неба" для hero-баннера
 * Вдохновлен компонентом SparklesCore из tsparticles
 */
document.addEventListener('DOMContentLoaded', function() {
  const heroSection = document.querySelector('.hero-section');
  if (!heroSection) return;
  
  // Создаем контейнер для частиц
  const particlesContainer = document.createElement('div');
  particlesContainer.className = 'particles-container';
  particlesContainer.style.cssText = `
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 1;
    pointer-events: none;
  `;
  
  // Добавляем контейнер в hero-секцию
  heroSection.style.position = 'relative';
  heroSection.appendChild(particlesContainer);
  
  // Параметры эффекта
  const config = {
    minSize: 1,
    maxSize: 3,
    minOpacity: 0.1,
    maxOpacity: 1,
    color: '#FFFFFF',
    quantity: 100,
    speed: 0.5,
  };
  
  // Создаем частицы
  for (let i = 0; i < config.quantity; i++) {
    createParticle(particlesContainer, config);
  }
  
  // Обработка клика для добавления новых частиц
  heroSection.addEventListener('click', function(e) {
    // Проверяем, что клик был непосредственно по hero-section, а не по другим элементам внутри
    if (e.target === heroSection || e.target === particlesContainer) {
      for (let i = 0; i < 5; i++) {
        createParticle(particlesContainer, config, e.clientX, e.clientY);
      }
    }
  });
});

/**
 * Создает одну частицу и добавляет её в контейнер
 */
function createParticle(container, config, x, y) {
  const particle = document.createElement('div');
  
  // Случайный размер
  const size = Math.random() * (config.maxSize - config.minSize) + config.minSize;
  
  // Случайная позиция
  const posX = x ? x - container.getBoundingClientRect().left : Math.random() * 100;
  const posY = y ? y - container.getBoundingClientRect().top : Math.random() * 100;
  
  // Случайная прозрачность
  const opacity = Math.random() * (config.maxOpacity - config.minOpacity) + config.minOpacity;
  
  // Время анимации
  const duration = (Math.random() * 20 + 10) / config.speed;
  
  // Стилизуем частицу
  particle.style.cssText = `
    position: absolute;
    width: ${size}px;
    height: ${size}px;
    border-radius: 50%;
    background-color: ${config.color};
    opacity: ${opacity};
    left: ${posX}px;
    top: ${posY}px;
    pointer-events: none;
    animation: float ${duration}s ease-in-out infinite;
  `;
  
  // Добавляем в контейнер
  container.appendChild(particle);
  
  // Случайное движение
  animateParticle(particle);
}

/**
 * Анимирует частицу для плавного движения
 */
function animateParticle(particle) {
  const maxDistance = 50; // Максимальная дистанция перемещения
  
  // Начальная позиция
  const startX = parseFloat(particle.style.left);
  const startY = parseFloat(particle.style.top);
  
  // Целевая позиция
  const targetX = startX + (Math.random() * maxDistance * 2 - maxDistance);
  const targetY = startY + (Math.random() * maxDistance * 2 - maxDistance);
  
  // Продолжительность
  const duration = Math.random() * 5 + 5; // 5-10 секунд
  
  // Анимация
  particle.animate(
    [
      { left: `${startX}px`, top: `${startY}px` },
      { left: `${targetX}px`, top: `${targetY}px` }
    ],
    {
      duration: duration * 1000,
      easing: 'ease-in-out',
      iterations: Infinity,
      direction: 'alternate'
    }
  );
}