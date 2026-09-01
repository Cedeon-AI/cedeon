import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const refresh = vi.fn();
const login = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api", () => ({
  login: (...args: unknown[]) => login(...args),
  asProblem: (v: unknown) => (v && typeof v === "object" ? v : null),
}));

import { LoginForm } from "@/components/auth/login-form";

describe("LoginForm", () => {
  beforeEach(() => {
    push.mockClear();
    refresh.mockClear();
    login.mockReset();
  });

  it("renders email and password fields", () => {
    render(<LoginForm />);
    expect(screen.getByLabelText(/work email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("submits credentials and navigates to the dashboard on success", async () => {
    login.mockResolvedValue({ data: { user: { id: "1" } } });
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText(/work email/i), "vp.ceded@carrier.example");
    await user.type(screen.getByLabelText(/password/i), "correct-horse-battery-staple");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(login).toHaveBeenCalledWith({
      body: {
        email: "vp.ceded@carrier.example",
        password: "correct-horse-battery-staple",
      },
    });
    expect(push).toHaveBeenCalledWith("/dashboard");
  });

  it("shows the problem detail on failure", async () => {
    login.mockResolvedValue({ error: { detail: "invalid email or password" } });
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText(/work email/i), "x@y.example");
    await user.type(screen.getByLabelText(/password/i), "wrong-password-value");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
