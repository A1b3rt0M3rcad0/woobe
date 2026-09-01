import { describe, expect, it } from 'vitest'
import {
  buildWoobeCalendarDays,
  isWoobeCalendarDayDisabled,
  mergeWoobeDateAndTime,
} from './WoobeDateTimePicker'


describe('WoobeDateTimePicker calendar logic', () => {
  it('builds a stable six-week calendar grid', () => {
    const days = buildWoobeCalendarDays(new Date(2026, 6, 1))

    expect(days).toHaveLength(42)
    expect(days[0].date.getDay()).toBe(0)
    expect(days.some((day) => day.outsideMonth)).toBe(true)
    expect(days.some((day) => day.date.getMonth() === 6 && day.date.getDate() === 9)).toBe(true)
  })

  it('disables previous days but keeps the current day selectable', () => {
    const minimum = new Date(2026, 6, 9, 14, 30)

    expect(isWoobeCalendarDayDisabled(new Date(2026, 6, 8), minimum)).toBe(true)
    expect(isWoobeCalendarDayDisabled(new Date(2026, 6, 9), minimum)).toBe(false)
    expect(isWoobeCalendarDayDisabled(new Date(2026, 6, 10), minimum)).toBe(false)
  })

  it('keeps the selected day and applies the chosen local time', () => {
    const merged = mergeWoobeDateAndTime(
      new Date(2026, 6, 24),
      new Date(2026, 0, 1, 18, 37, 45, 999),
    )

    expect(merged.getFullYear()).toBe(2026)
    expect(merged.getMonth()).toBe(6)
    expect(merged.getDate()).toBe(24)
    expect(merged.getHours()).toBe(18)
    expect(merged.getMinutes()).toBe(37)
    expect(merged.getSeconds()).toBe(0)
    expect(merged.getMilliseconds()).toBe(0)
  })
})
