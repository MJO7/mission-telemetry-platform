import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorMessage } from "./StatusMessage";
import { ApiError } from "../api/client";

describe("ErrorMessage", () => {
  it("shows a friendly message for a 401", () => {
    render(<ErrorMessage error={new ApiError(401, null)} />);
    expect(screen.getByText(/session expired/i)).toBeInTheDocument();
  });

  it("shows a friendly message for a 403", () => {
    render(<ErrorMessage error={new ApiError(403, null)} />);
    expect(screen.getByText(/don't have permission/i)).toBeInTheDocument();
  });

  it("surfaces the backend's detail message when present", () => {
    render(<ErrorMessage error={new ApiError(404, { detail: "vehicle not found" })} />);
    expect(screen.getByText("vehicle not found")).toBeInTheDocument();
  });

  it("falls back to a generic message for an unrecognized status", () => {
    render(<ErrorMessage error={new ApiError(500, null)} />);
    expect(screen.getByText("Request failed (500).")).toBeInTheDocument();
  });

  it("falls back to the error's own message for a plain Error", () => {
    render(<ErrorMessage error={new Error("network down")} />);
    expect(screen.getByText("network down")).toBeInTheDocument();
  });
});
