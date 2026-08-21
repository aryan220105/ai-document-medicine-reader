import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanguageSelector } from "../components/LanguageSelector";
import { EasyReadToggle } from "../components/EasyReadToggle";

describe("LanguageSelector", () => {
  it("changes language", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<LanguageSelector value="en" onChange={onChange} />);
    await user.selectOptions(screen.getByLabelText("Answer language"), "hi");
    expect(onChange).toHaveBeenCalledWith("hi");
  });
});

describe("EasyReadToggle", () => {
  it("toggles easy read", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<EasyReadToggle value={false} onChange={onChange} />);
    await user.click(screen.getByLabelText("Easy Read Mode"));
    expect(onChange).toHaveBeenCalledWith(true);
  });
});
