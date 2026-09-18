import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import { DashboardMetrics } from "@/components/board/DashboardView";
import type { Dashboard } from "@/lib/api";

const populated: Dashboard = {
  board_id: 1,
  total: 14,
  by_column: [
    { column_id: 1, name: "Backlog", position: 0, count: 2 },
    { column_id: 2, name: "To Do", position: 1, count: 3 },
    { column_id: 5, name: "Done", position: 4, count: 2 },
  ],
  overdue: 3,
  done: 2,
  progress_percent: 14.3,
};

describe("DashboardMetrics", () => {
  test("renders the four metrics, the progress bar and counts by column", () => {
    render(<DashboardMetrics data={populated} />);

    expect(screen.getByText("Total tasks").nextElementSibling?.textContent).toBe("14");
    expect(screen.getByText("Overdue").nextElementSibling?.textContent).toBe("3");
    expect(screen.getByText("Done", { selector: "p" }).nextElementSibling?.textContent).toBe("2");
    expect(screen.getByText("Progress").nextElementSibling?.textContent).toBe("14.3%");
    const bar = screen.getByRole("progressbar", { name: "Progress" });
    expect(bar.getAttribute("aria-valuenow")).toBe("14");
    expect(screen.getByText("2 of 14 tasks done.")).toBeDefined();
    const rows = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(rows).toEqual(["Backlog2", "To Do3", "Done2"]);
  });

  test("zero-task state", () => {
    render(
      <DashboardMetrics
        data={{ ...populated, total: 0, overdue: 0, done: 0, progress_percent: 0, by_column: populated.by_column.map((c) => ({ ...c, count: 0 })) }}
      />,
    );

    expect(screen.getByText("Total tasks").nextElementSibling?.textContent).toBe("0");
    expect(screen.getByText("Progress").nextElementSibling?.textContent).toBe("0%");
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("0");
    expect(screen.getByText("No tasks yet.")).toBeDefined();
  });
});
