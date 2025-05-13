import "../styles/globals.css";
import { Metadata } from "next";
import React, { ReactNode } from "react";

export const metadata: Metadata = {
  title: "RunTrainer.AI - Персональные планы тренировок для бегунов",
  description: "Телеграм-бот с искусственным интеллектом для создания персонализированных планов тренировок для бегунов",
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="ru">
      <body>
        {children}
      </body>
    </html>
  );
}