import assert from "node:assert/strict";
import { test } from "node:test";
import { addDaysIso, crossesMidnight, currentShiftDay, dayAsText, dayLayout, loggedCount, scheduleSlots,
  slotLabel, windowDays } from "../lib/worklog.ts";

test("schedule slots cover the working hours and wrap past midnight", () => {
  assert.deepEqual(scheduleSlots(9, 18), [9, 10, 11, 12, 13, 14, 15, 16, 17]);
  assert.deepEqual(scheduleSlots(22, 6), [22, 23, 0, 1, 2, 3, 4, 5]);
  assert.equal(scheduleSlots(6, 6).length, 24);
  assert.equal(scheduleSlots(0, 24).length, 24);
  assert.deepEqual(scheduleSlots(23, 24), [23]);
  assert.equal(crossesMidnight(22, 6), true);
  assert.equal(crossesMidnight(9, 18), false);
});

test("slot labels are 24h ranges that wrap at midnight", () => {
  assert.equal(slotLabel(13), "13:00-14:00");
  assert.equal(slotLabel(9), "09:00-10:00");
  assert.equal(slotLabel(23), "23:00-00:00");
});

test("window is today and the 6 previous days, across month and year ends", () => {
  assert.deepEqual(windowDays("2026-10-21"), [
    "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21",
  ]);
  assert.equal(windowDays("2026-01-03")[0], "2025-12-28");
  assert.equal(addDaysIso("2026-03-01", -1), "2026-02-28");
});

test("a night shift stays on the previous day until it ends", () => {
  assert.equal(currentShiftDay(new Date(2026, 9, 21, 1, 30), 22, 6), "2026-10-20");
  assert.equal(currentShiftDay(new Date(2026, 9, 21, 5, 59), 22, 6), "2026-10-20");
  assert.equal(currentShiftDay(new Date(2026, 9, 21, 6, 0), 22, 6), "2026-10-21");
  assert.equal(currentShiftDay(new Date(2026, 9, 21, 23, 0), 22, 6), "2026-10-21");
  assert.equal(currentShiftDay(new Date(2026, 9, 21, 1, 0), 9, 18), "2026-10-21");
});

test("entries outside the schedule are kept visible after the schedule changes", () => {
  const notes = new Map([[9, "standup"], [2, "deploy"], [23, "hotfix"], [10, "   "]]);
  const layout = dayLayout([22, 23, 0, 1], notes);
  assert.deepEqual(layout.extra, [2, 9]);
  assert.equal(loggedCount([22, 23, 0, 1], notes), 1);
  assert.equal(loggedCount([9, 10], notes), 1);
});

test("copy text lists logged hours only and indents multi-line notes", () => {
  const notes = new Map([[13, "Fixed login bug\nadded test"], [14, ""], [15, "Review"]]);
  const layout = dayLayout([13, 14, 15], notes);
  assert.equal(
    dayAsText("Work log - Wed, Oct 21", layout, notes),
    "Work log - Wed, Oct 21\n13:00-14:00 - Fixed login bug\n            added test\n15:00-16:00 - Review",
  );
});
