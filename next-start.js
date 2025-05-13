#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');

console.log('Starting Next.js development server...');

// Запускаем Next.js dev сервер
const nextProcess = spawn('npx', ['next', 'dev', '-p', '3000'], {
  stdio: 'inherit',
  shell: true
});

// Обработка выхода из процесса
process.on('SIGINT', () => {
  console.log('Stopping Next.js server...');
  nextProcess.kill('SIGINT');
  process.exit(0);
});

nextProcess.on('close', (code) => {
  console.log(`Next.js process exited with code ${code}`);
  process.exit(code);
});