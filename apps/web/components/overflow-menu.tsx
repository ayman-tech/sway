"use client";

import type { LucideIcon } from "lucide-react";
import { MoreVertical } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export type OverflowAction = {
  label: string;
  icon: LucideIcon;
  onSelect: () => void | Promise<unknown>;
  danger?: boolean;
  disabled?: boolean;
};

export function OverflowMenu({ actions, label = "More actions" }: { actions: OverflowAction[]; label?: string }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div className="relative" ref={rootRef}>
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={label}
        className="icon-button"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((current) => !current);
        }}
        type="button"
      >
        <MoreVertical size={20} />
      </button>
      {open ? (
        <div className="overflow-menu" role="menu">
          {actions.map((action) => (
            <button
              className={action.danger ? "overflow-menu-danger" : ""}
              disabled={action.disabled}
              key={action.label}
              onClick={async (event) => {
                event.stopPropagation();
                await action.onSelect();
                setOpen(false);
              }}
              role="menuitem"
              type="button"
            >
              <action.icon size={17} />
              {action.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
