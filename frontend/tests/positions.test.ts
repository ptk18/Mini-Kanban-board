import { describe, expect, test } from "vitest";
import { applyCardMove, applyColumnMove, computeCardDrop, computeColumnDrop } from "@/lib/positions";

// Two columns: 10 holds a(0) b(1) c(2); 11 holds x(0) y(1); 12 is empty.
const cards = [
  { id: 1, column_id: 10, position: 0 }, // a
  { id: 2, column_id: 10, position: 1 }, // b
  { id: 3, column_id: 10, position: 2 }, // c
  { id: 4, column_id: 11, position: 0 }, // x
  { id: 5, column_id: 11, position: 1 }, // y
];
const columns = [
  { id: 10, position: 0 },
  { id: 11, position: 1 },
  { id: 12, position: 2 },
];

const layout = (list: { id: number; column_id: number; position: number }[]) =>
  Object.fromEntries(
    [10, 11, 12].map((col) => [
      col,
      list.filter((c) => c.column_id === col).sort((a, b) => a.position - b.position).map((c) => c.id),
    ]),
  );

describe("computeCardDrop within a column", () => {
  test("dragging down onto a later card lands after it", () => {
    expect(computeCardDrop(cards, 1, { type: "card", id: 3 })).toEqual({ column_id: 10, position: 2 });
    expect(computeCardDrop(cards, 1, { type: "card", id: 2 })).toEqual({ column_id: 10, position: 1 });
  });

  test("dragging up onto an earlier card lands before it", () => {
    expect(computeCardDrop(cards, 3, { type: "card", id: 1 })).toEqual({ column_id: 10, position: 0 });
    expect(computeCardDrop(cards, 3, { type: "card", id: 2 })).toEqual({ column_id: 10, position: 1 });
  });

  test("dropping on itself, or where it already is, is a no-op", () => {
    expect(computeCardDrop(cards, 2, { type: "card", id: 2 })).toBeNull();
    expect(computeCardDrop(cards, 3, { type: "column", id: 10 })).toBeNull();
  });

  test("dropping on the own column appends", () => {
    expect(computeCardDrop(cards, 1, { type: "column", id: 10 })).toEqual({ column_id: 10, position: 2 });
  });
});

describe("computeCardDrop across columns", () => {
  test("dropping on a card in another column inserts before it", () => {
    expect(computeCardDrop(cards, 1, { type: "card", id: 5 })).toEqual({ column_id: 11, position: 1 });
    expect(computeCardDrop(cards, 1, { type: "card", id: 4 })).toEqual({ column_id: 11, position: 0 });
  });

  test("dropping on another column appends; an empty column takes position 0", () => {
    expect(computeCardDrop(cards, 1, { type: "column", id: 11 })).toEqual({ column_id: 11, position: 2 });
    expect(computeCardDrop(cards, 1, { type: "column", id: 12 })).toEqual({ column_id: 12, position: 0 });
  });

  test("unknown ids are ignored", () => {
    expect(computeCardDrop(cards, 99, { type: "column", id: 11 })).toBeNull();
    expect(computeCardDrop(cards, 1, { type: "card", id: 99 })).toBeNull();
  });
});

describe("applyCardMove mirrors the server", () => {
  test("reorder within a column renumbers contiguously", () => {
    const next = applyCardMove(cards, 1, { column_id: 10, position: 2 });
    expect(layout(next)).toEqual({ 10: [2, 3, 1], 11: [4, 5], 12: [] });
    expect(next.filter((c) => c.column_id === 10).map((c) => c.position).sort()).toEqual([0, 1, 2]);
  });

  test("move across columns renumbers both columns", () => {
    const next = applyCardMove(cards, 2, { column_id: 11, position: 1 });
    expect(layout(next)).toEqual({ 10: [1, 3], 11: [4, 2, 5], 12: [] });
    expect(next.find((c) => c.id === 3)?.position).toBe(1);
    expect(next.find((c) => c.id === 5)?.position).toBe(2);
  });

  test("every computed drop applied locally matches the drop target", () => {
    for (const active of [1, 2, 3, 4, 5]) {
      for (const over of [1, 2, 3, 4, 5]) {
        const move = computeCardDrop(cards, active, { type: "card", id: over });
        if (!move) continue;
        const next = applyCardMove(cards, active, move);
        const column = layout(next)[move.column_id];
        expect(column[move.position]).toBe(active);
      }
    }
  });
});

describe("columns", () => {
  test("computeColumnDrop is the index of the column dropped on", () => {
    expect(computeColumnDrop(columns, 10, 12)).toBe(2);
    expect(computeColumnDrop(columns, 12, 10)).toBe(0);
    expect(computeColumnDrop(columns, 11, 11)).toBeNull();
    expect(computeColumnDrop(columns, 99, 10)).toBeNull();
  });

  test("applyColumnMove matches arrayMove semantics and renumbers", () => {
    expect(applyColumnMove(columns, 10, 2).map((c) => c.id)).toEqual([11, 12, 10]);
    expect(applyColumnMove(columns, 12, 0).map((c) => [c.id, c.position])).toEqual([[12, 0], [10, 1], [11, 2]]);
  });
});
