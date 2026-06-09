import { cn } from "@/lib/utils";
import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function Field({
  label,
  hint,
  required,
  children,
  className,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
        {required && <span className="ml-1 text-primary">*</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-subtle">{hint}</span>}
    </label>
  );
}

const inputBase =
  "w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-subtle focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(inputBase, className)} {...props} />;
}

export function Select({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(inputBase, "appearance-none", className)} {...props}>
      {children}
    </select>
  );
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(inputBase, "min-h-[80px] resize-y", className)} {...props} />;
}

export function SubmitButton({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="submit"
      className={cn(
        "rounded-md px-5 py-2.5 text-sm font-bold uppercase tracking-wider text-white shadow-fbf-btn transition-transform hover:scale-[1.01] active:scale-[0.99]",
        className,
      )}
      style={{ background: "linear-gradient(135deg, #ff6a00, #ff8c00, #e85d00)" }}
    >
      {children}
    </button>
  );
}

export function AddNewSection({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details
      open={defaultOpen}
      className="group fbf-card !p-0 overflow-hidden"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4 transition-colors hover:bg-surface-2">
        <span className="flex items-center gap-3">
          <span
            aria-hidden
            className="grid h-7 w-7 place-items-center rounded-md text-base font-bold leading-none text-white shadow-fbf-glow-sm"
            style={{ background: "linear-gradient(135deg, #ff6a00, #e85d00)" }}
          >
            +
          </span>
          <span className="text-sm font-semibold">{title}</span>
        </span>
        <span className="text-xs uppercase tracking-wider text-muted-foreground group-open:text-primary">
          <span className="group-open:hidden">Open</span>
          <span className="hidden group-open:inline">Close</span>
        </span>
      </summary>
      <div className="border-t border-border bg-surface-2/60 p-5">{children}</div>
    </details>
  );
}
