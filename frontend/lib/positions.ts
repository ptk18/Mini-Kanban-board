/**
 * Position calculation for drag-and-drop (issue #24).
 *
 * The backend keeps positions 0-based and contiguous: a card PATCH with
 * `{column_id, position}` removes the card from its column and inserts it at
 * `position` among the remaining cards of the target column; a column PATCH
 * with `{position}` does the same among the board's columns. These helpers
 * turn a drop (what was dragged, what it was dropped on) into exactly that
 * request, and apply the same move locally for the optimistic update.
 */

export type Positioned = { id: number; position: number };
export type CardLike = Positioned & { column_id: number };

export type DropTarget =
  | { type: "card"; id: number }
  | { type: "column"; id: number };

export type CardMove = { column_id: number; position: number };

function byPosition<T extends Positioned>(items: T[]): T[] {
  return [...items].sort((a, b) => a.position - b.position || a.id - b.id);
}

/**
 * Where a dragged card lands. Dropping on a card inserts before it (after it
 * when moving down within the same column, matching the visual sortable
 * preview); dropping on a column appends. Returns null for a no-op.
 */
export function computeCardDrop(
  cards: CardLike[],
  activeId: number,
  target: DropTarget,
): CardMove | null {
  const active = cards.find((c) => c.id === activeId);
  if (!active) return null;

  if (target.type === "column") {
    const siblings = byPosition(cards.filter((c) => c.column_id === target.id && c.id !== activeId));
    const position = siblings.length;
    if (active.column_id === target.id && active.position === position) return null;
    return { column_id: target.id, position };
  }

  if (target.id === activeId) return null;
  const over = cards.find((c) => c.id === target.id);
  if (!over) return null;
  const sameColumn = over.column_id === active.column_id;
  const siblings = byPosition(cards.filter((c) => c.column_id === over.column_id && c.id !== activeId));
  const index = siblings.findIndex((c) => c.id === over.id);
  const position = index + (sameColumn && active.position < over.position ? 1 : 0);
  if (sameColumn && position === active.position) return null;
  return { column_id: over.column_id, position };
}

/** The `position` for a column PATCH when `activeId` is dropped on `overId`. */
export function computeColumnDrop(
  columns: Positioned[],
  activeId: number,
  overId: number,
): number | null {
  if (activeId === overId) return null;
  const ordered = byPosition(columns);
  const from = ordered.findIndex((c) => c.id === activeId);
  const to = ordered.findIndex((c) => c.id === overId);
  if (from === -1 || to === -1) return null;
  return to;
}

/** The card list as the server will hold it after `move` (optimistic view). */
export function applyCardMove<T extends CardLike>(cards: T[], activeId: number, move: CardMove): T[] {
  const active = cards.find((c) => c.id === activeId);
  if (!active) return cards;
  const others = cards.filter((c) => c.id !== activeId);
  const source = byPosition(others.filter((c) => c.column_id === active.column_id));
  const target =
    move.column_id === active.column_id
      ? source
      : byPosition(others.filter((c) => c.column_id === move.column_id));
  const untouched = others.filter(
    (c) => c.column_id !== active.column_id && c.column_id !== move.column_id,
  );
  const moved = { ...active, column_id: move.column_id };
  const targetWithActive = [...target];
  targetWithActive.splice(Math.min(move.position, target.length), 0, moved);
  const renumber = (list: T[]) => list.map((c, position) => ({ ...c, position }));
  return [
    ...untouched,
    ...(move.column_id === active.column_id ? [] : renumber(source)),
    ...renumber(targetWithActive),
  ];
}

/** The column list after moving `activeId` to index `position`. */
export function applyColumnMove<T extends Positioned>(columns: T[], activeId: number, position: number): T[] {
  const ordered = byPosition(columns);
  const from = ordered.findIndex((c) => c.id === activeId);
  if (from === -1) return columns;
  const [active] = ordered.splice(from, 1);
  ordered.splice(Math.min(position, ordered.length), 0, active);
  return ordered.map((c, index) => ({ ...c, position: index }));
}
