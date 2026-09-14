import { clsx, type ClassValue } from 'clsx'
import { mergeWoobeClasses } from '@woobe/ui'

export function cn(...inputs: ClassValue[]) {
  return mergeWoobeClasses(clsx(inputs))
}
