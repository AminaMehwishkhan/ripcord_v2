import type { ReactNode } from "react";

export function Card({ title, right, children, className = "" }: {
  title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`card card-pad ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 mb-3">
          <h3 className="card-title">{title}</h3>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}
