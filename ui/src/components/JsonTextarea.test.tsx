import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { JsonTextarea } from "./JsonTextarea";

describe("JsonTextarea", () => {
  it("preserves invalid draft text and only emits parsed JSON when valid", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <JsonTextarea
        label="Style overrides JSON"
        value={{ theme: "meli" }}
        onChange={onChange}
      />,
    );

    const input = screen.getByLabelText("Style overrides JSON");
    fireEvent.change(input, { target: { value: "{" } });

    expect(input).toHaveValue("{");
    expect(screen.getByText("Enter valid JSON before leaving this field.")).toBeInTheDocument();

    await user.clear(input);
    fireEvent.change(input, { target: { value: '{"theme":"latam"}' } });

    expect(onChange).toHaveBeenLastCalledWith({ theme: "latam" });
  });
});
