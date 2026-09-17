import { test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Page from "@/app/page";

test("home page renders the Mini Kanban heading", () => {
  render(<Page />);
  expect(
    screen.getByRole("heading", { level: 1, name: "Mini Kanban" }),
  ).toBeDefined();
});
