#!/bin/bash

# Запуск React-лендинга с Next.js
echo "Starting React landing page with Next.js..."
cd $(dirname "$0") # переход в директорию скрипта
exec node next-start.js