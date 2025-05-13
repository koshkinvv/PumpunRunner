"use client";

import React from "react";
import { SparklesCore } from "../components/ui/sparkles";
import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center">
      {/* Секция Hero с эффектом звездного неба */}
      <section className="relative flex h-screen w-full flex-col items-center justify-center overflow-hidden bg-black">
        <div className="absolute inset-0 z-0">
          <SparklesCore
            id="tsparticlesfullpage"
            background="transparent"
            minSize={0.5}
            maxSize={1.5}
            particleColor="#FFFFFF"
            particleDensity={100}
            speed={0.5}
            className="h-full w-full"
          />
        </div>

        <div className="relative z-10 flex flex-col items-center justify-center px-5 text-center">
          <h1 className="mb-8 text-6xl font-bold tracking-tight text-white md:text-8xl">
            RunTrainer.AI
          </h1>
          <p className="mb-12 max-w-3xl text-lg text-gray-300 md:text-xl">
            Искусственный интеллект создаст персональный план тренировок, 
            учитывающий вашу физическую форму, цели и расписание
          </p>
          <div className="flex flex-col space-y-4 sm:flex-row sm:space-x-4 sm:space-y-0">
            <Link
              href="https://t.me/RunTrainerBot"
              className="btn-primary"
              target="_blank"
              rel="noopener noreferrer"
            >
              Начать в Telegram
            </Link>
            <button className="btn-secondary">
              Подробнее
            </button>
          </div>
        </div>
      </section>

      {/* Секция О продукте */}
      <section className="w-full bg-gray-900 py-20">
        <div className="container mx-auto px-5">
          <h2 className="mb-12 text-center text-4xl font-bold text-white">
            Персональный тренер в вашем телефоне
          </h2>
          <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
            <div className="rounded-lg bg-gray-800 p-6">
              <h3 className="mb-3 text-xl font-semibold text-white">
                Персонализация
              </h3>
              <p className="text-gray-300">
                Индивидуальный план тренировок, учитывающий вашу физическую форму, 
                цели и график
              </p>
            </div>
            <div className="rounded-lg bg-gray-800 p-6">
              <h3 className="mb-3 text-xl font-semibold text-white">
                Адаптация
              </h3>
              <p className="text-gray-300">
                План автоматически корректируется на основе ваших результатов и 
                обратной связи
              </p>
            </div>
            <div className="rounded-lg bg-gray-800 p-6">
              <h3 className="mb-3 text-xl font-semibold text-white">
                Поддержка
              </h3>
              <p className="text-gray-300">
                Получайте напоминания о тренировках и советы по улучшению результатов
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Секция Регистрация */}
      <section className="w-full bg-black py-20">
        <div className="container mx-auto px-5 text-center">
          <h2 className="mb-8 text-4xl font-bold text-white">
            Начните тренироваться уже сегодня
          </h2>
          <p className="mx-auto mb-12 max-w-3xl text-lg text-gray-300">
            Первые 7 дней бесплатно, затем всего 500 рублей в месяц за персонального 
            тренера на базе искусственного интеллекта
          </p>
          <Link
            href="https://t.me/RunTrainerBot"
            className="btn-primary"
            target="_blank"
            rel="noopener noreferrer"
          >
            Начать в Telegram
          </Link>
        </div>
      </section>

      {/* Футер */}
      <footer className="w-full bg-gray-900 py-10">
        <div className="container mx-auto px-5 text-center">
          <p className="text-gray-400">
            © 2025 RunTrainer.AI | Все права защищены
          </p>
        </div>
      </footer>
    </main>
  );
}