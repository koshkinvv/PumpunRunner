import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export type ClassValue = string | number | boolean | undefined | null | Record<string, unknown> | ClassValue[];

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}