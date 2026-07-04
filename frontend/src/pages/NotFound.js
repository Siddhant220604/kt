import React from 'react';
import { Link } from 'react-router-dom';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';

export default function NotFound() {
  return (
    <Section>
      <Container className="text-center py-16">
        <div className="font-display font-bold text-7xl text-[hsl(var(--brand-terracotta))]">404</div>
        <h1 className="text-2xl font-display font-bold mt-2">Page not found</h1>
        <p className="text-muted-foreground mt-2">The page you're looking for doesn't exist.</p>
        <Link to="/"><Button className="mt-6">Go home</Button></Link>
      </Container>
    </Section>
  );
}
