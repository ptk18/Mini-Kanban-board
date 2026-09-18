// Vitest runs without `globals`, so Testing Library cannot register its own
// afterEach cleanup; do it here so renders never leak between tests.
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(cleanup);
