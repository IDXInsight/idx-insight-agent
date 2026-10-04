"use client";

import * as React from "react";
import { GripVertical, RotateCcw } from "lucide-react";
import { MotionConfig, Reorder, useDragControls } from "motion/react";
import { type Lang, t } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type DraggableWidgetGridProps = {
  children: React.ReactNode;
  storageKey: string;
  lang: Lang;
  labels?: Record<string, string>;
  className?: string;
  axis?: "x" | "y" | "xy";
};

function reconcile(saved: string[], visible: string[]): string[] {
  const set = new Set(visible);
  return [...new Set([...saved.filter(id => set.has(id)), ...visible])];
}

function readOrder(key: string): string[] {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(key) ?? "null");
    return Array.isArray(value) && value.every(id => typeof id === "string") ? value : [];
  } catch {
    return [];
  }
}

function saveOrder(key: string, ids: string[]) {
  try { window.localStorage.setItem(key, JSON.stringify(ids)); } catch { /* Layout remains available for this visit. */ }
}

function WidgetSlot({ id, label, children, lang, movable, onMove }: {
  id: string;
  label: string;
  children: React.ReactNode;
  lang: Lang;
  movable: boolean;
  onMove: (id: string, delta: number) => void;
}) {
  const controls = useDragControls();
  return <Reorder.Item
    as="div"
    value={id}
    dragListener={false}
    dragControls={controls}
    dragMomentum={false}
    role="listitem"
    className="widget-slot"
    data-widget-id={id}
    whileDrag={{ scale: 1.015, boxShadow: "0 18px 45px #0008" }}
  >
    {movable && <button
      type="button"
      className="widget-drag-handle"
      aria-label={t(lang, "widgets.move", { name: label })}
      title={t(lang, "widgets.move", { name: label })}
      onPointerDown={event => { if (event.isPrimary && event.button === 0) controls.start(event); }}
      onKeyDown={event => {
        if (!event.altKey || (event.key !== "ArrowUp" && event.key !== "ArrowDown")) return;
        event.preventDefault();
        event.stopPropagation();
        onMove(id, event.key === "ArrowUp" ? -1 : 1);
      }}
    ><GripVertical size={14} aria-hidden="true" /></button>}
    {children}
  </Reorder.Item>;
}

/** Reorders real, variable-height cards without cropping tables, charts, or event lists. */
export function DraggableWidgetGrid({ children, storageKey, lang, labels = {}, className, axis = "y" }: DraggableWidgetGridProps) {
  const elements = React.Children.toArray(children).filter(React.isValidElement);
  const visible = elements.map(element => String(element.key));
  const visibleSignature = visible.join("\u0000");
  const [saved, setSaved] = React.useState<string[]>(visible);

  React.useEffect(() => {
    let active = true;
    queueMicrotask(() => { if (active) setSaved(reconcile(readOrder(storageKey), visible)); });
    return () => { active = false; };
    // The signature changes only when widget identities change, not when live data refreshes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey, visibleSignature]);

  const order = reconcile(saved, visible);
  const byId = new Map(elements.map((element, index) => [visible[index], element]));
  const changed = order.some((id, index) => id !== visible[index]);

  function commit(next: string[]) {
    const valid = reconcile(next, visible);
    setSaved(valid);
    saveOrder(storageKey, valid);
  }

  function move(id: string, delta: number) {
    const from = order.indexOf(id);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= order.length) return;
    const next = [...order];
    next.splice(from, 1);
    next.splice(to, 0, id);
    commit(next);
  }

  return <MotionConfig reducedMotion="user">
    <div className={cn("widget-grid", className)}>
      {order.length > 1 && <div className="widget-grid-toolbar">
        <span>{t(lang, "widgets.hint")}</span>
        {changed && <button type="button" className="widget-reset" onClick={() => {
          setSaved(visible);
          try { window.localStorage.removeItem(storageKey); } catch { /* Keep the current reset order. */ }
        }}><RotateCcw size={12} aria-hidden="true" />{t(lang, "widgets.reset")}</button>}
      </div>}
      <Reorder.Group as="div" axis={axis} values={order} onReorder={commit} role="list"
        aria-label={t(lang, "widgets.group")} className="widget-reorder-group">
        {order.map(id => {
          const element = byId.get(id);
          if (!element) return null;
          const plainId = id.replace(/^.*\$/, "");
          return <WidgetSlot key={id} id={id} label={labels[plainId] ?? plainId} lang={lang}
            movable={order.length > 1} onMove={move}>{element}</WidgetSlot>;
        })}
      </Reorder.Group>
    </div>
  </MotionConfig>;
}
