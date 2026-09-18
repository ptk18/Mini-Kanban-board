import type { Active, Over } from "@dnd-kit/core";
import type { DropTarget } from "@/lib/positions";

/** What a draggable/droppable carries in its `data`. */
export type DragData = { type: "card"; id: number } | { type: "column"; id: number };

export const cardDragId = (id: number) => `card-${id}`;
export const columnDragId = (id: number) => `column-${id}`;
export const columnDropId = (id: number) => `column-drop-${id}`;

export function dragData(node: Active | Over | null): DragData | null {
  const data = node?.data.current as DragData | undefined;
  return data && (data.type === "card" || data.type === "column") ? data : null;
}

export function asDropTarget(node: Over | null): DropTarget | null {
  const data = dragData(node);
  return data ? { type: data.type, id: data.id } : null;
}
