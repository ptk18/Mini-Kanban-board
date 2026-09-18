import { describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { buildCardQuery } from "@/lib/api";
import { BoardToolbar, activeFilterCount } from "@/components/board/BoardToolbar";
import { columns, members } from "./fixtures";

describe("buildCardQuery", () => {
  test("is empty with no filters", () => {
    expect(buildCardQuery({})).toBe("");
    expect(buildCardQuery({ q: "  ", column_id: null, priority: "", assignee_id: null })).toBe("");
  });

  test("includes each selected filter, trimmed and encoded", () => {
    expect(buildCardQuery({ q: " login bug " })).toBe("?q=login+bug");
    expect(buildCardQuery({ column_id: 10 })).toBe("?column_id=10");
    expect(buildCardQuery({ priority: "high" })).toBe("?priority=high");
    expect(buildCardQuery({ assignee_id: 2 })).toBe("?assignee_id=2");
  });

  test("combines every filter in a stable order", () => {
    expect(buildCardQuery({ q: "100%", column_id: 10, priority: "low", assignee_id: 2 })).toBe(
      "?q=100%25&column_id=10&priority=low&assignee_id=2",
    );
  });
});

describe("BoardToolbar", () => {
  test("selecting filters reports them and shows the active count; Clear resets", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <BoardToolbar filters={{}} columns={columns} members={members} onChange={onChange} />,
    );
    expect(screen.queryByTestId("active-filter-count")).toBeNull();

    fireEvent.change(screen.getByLabelText("Filter by priority"), { target: { value: "high" } });
    expect(onChange).toHaveBeenLastCalledWith({ priority: "high" });

    fireEvent.change(screen.getByLabelText("Filter by assignee"), { target: { value: "2" } });
    expect(onChange).toHaveBeenLastCalledWith({ assignee_id: 2 });

    const filters = { q: "bug", priority: "high" as const, column_id: 10 };
    rerender(<BoardToolbar filters={filters} columns={columns} members={members} onChange={onChange} />);
    expect(screen.getByTestId("active-filter-count").textContent).toBe("3 filters active");
    expect(activeFilterCount(filters)).toBe(3);
    expect(buildCardQuery(filters)).toBe("?q=bug&column_id=10&priority=high");

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onChange).toHaveBeenLastCalledWith({});
  });
});
