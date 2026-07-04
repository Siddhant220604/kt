import React from 'react';
export const Section = ({ children, className = '', ...p }) => (
  <section className={`py-10 sm:py-14 ${className}`} {...p}>{children}</section>
);
export const Container = ({ children, className = '', ...p }) => (
  <div className={`max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 ${className}`} {...p}>{children}</div>
);
export const SectionTitle = ({ eyebrow, title, subtitle, action, center }) => (
  <div className={`mb-8 flex flex-col ${center ? 'items-center text-center' : 'md:flex-row md:items-end md:justify-between'} gap-4`}>
    <div>
      {eyebrow && <div className="text-xs uppercase tracking-widest text-[hsl(var(--brand-terracotta))] font-semibold mb-1">{eyebrow}</div>}
      <h2 className="text-2xl sm:text-3xl md:text-4xl font-display font-bold">{title}</h2>
      {subtitle && <p className="text-sm sm:text-base text-muted-foreground mt-2 max-w-2xl">{subtitle}</p>}
    </div>
    {action}
  </div>
);
